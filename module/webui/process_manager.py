import argparse
import os
import queue
import threading
import time
from multiprocessing import Process
from typing import Dict, List, Union

import inflection
from rich.console import Console, ConsoleRenderable

# Since this file does not run under the same process or subprocess of app.py
# the following code needs to be repeated
# Import fake module before import pywebio to avoid importing unnecessary module PIL
from module.webui.fake_pil_module import *

import_fake_pil_module()

from module.logger import logger, set_file_logger, set_func_logger
from module.submodule.submodule import load_mod
from module.submodule.utils import get_available_func, get_available_mod, get_available_mod_func, get_config_mod, \
    get_func_mod, list_mod_instance
from module.webui.setting import State


class ProcessManager:
    _processes: Dict[str, "ProcessManager"] = {}

    def __init__(self, config_name: str = "alas") -> None:
        self.config_name = config_name
        self._renderable_queue: queue.Queue[ConsoleRenderable] = State.manager.Queue()
        self.renderables: List[ConsoleRenderable] = []
        self.renderables_max_length = 400
        self.renderables_reduce_length = 80
        self._process: Process = None
        self._process_locks: Dict[str, threading.Lock] = {}
        self.thd_log_queue_handler: threading.Thread = None
        self.ev: threading.Event = None
        self.in_active_task: bool = False
        self.thd_watchdog: threading.Thread = None
        self._watchdog_stop_event = threading.Event()
        self.last_activity_time = time.time()
        self.last_main_process_trim_time = time.time()

    def start(self, func, ev: threading.Event = None) -> None:
        if ev is not None:
            self.ev = ev
        if not self.alive:
            if func is None:
                func = get_config_mod(self.config_name)
            self._process = Process(
                target=ProcessManager.run_process,
                args=(
                    self.config_name,
                    func,
                    self._renderable_queue,
                    self.ev,
                ),
            )
            self._process.start()
            self.last_activity_time = time.time()
            self.in_active_task = False
            self.start_log_queue_handler()
            self.start_watchdog()

    def start_log_queue_handler(self):
        if (
            self.thd_log_queue_handler is not None
            and self.thd_log_queue_handler.is_alive()
        ):
            return
        self.thd_log_queue_handler = threading.Thread(
            target=self._thread_log_queue_handler
        )
        self.thd_log_queue_handler.start()

    def start_watchdog(self):
        if (
            self.thd_watchdog is not None
            and self.thd_watchdog.is_alive()
        ):
            return
        self._watchdog_stop_event.clear()
        self.thd_watchdog = threading.Thread(
            target=self._thread_watchdog,
            daemon=True
        )
        self.thd_watchdog.start()

    def stop(self) -> None:
        try:
            lock = self._process_locks[self.config_name]
        except KeyError:
            lock = threading.Lock()
            self._process_locks[self.config_name] = lock

        with lock:
            self._watchdog_stop_event.set()
            if self.thd_watchdog is not None:
                self.thd_watchdog.join(timeout=1)
                if self.thd_watchdog.is_alive():
                    logger.warning("Watchdog thread does not stop within 1 seconds")

            if self.alive:
                self._process.kill()
                self.renderables.append(
                    f"[{self.config_name}] exited. Reason: Manual stop\n"
                )
            if self.thd_log_queue_handler is not None:
                self.thd_log_queue_handler.join(timeout=1)
                if self.thd_log_queue_handler.is_alive():
                    logger.warning(
                        "Log queue handler thread does not stop within 1 seconds"
                    )
        logger.info(f"[{self.config_name}] exited")

    def _renderable_to_str(self, renderable) -> str:
        if isinstance(renderable, str):
            return renderable
        if hasattr(renderable, 'plain'):
            return renderable.plain
        try:
            console = Console(no_color=True)
            with console.capture() as capture:
                console.print(renderable)
            return capture.get().strip()
        except Exception:
            return str(renderable)

    def _update_task_state_from_log(self, log) -> None:
        s = self._renderable_to_str(log)
        if "Scheduler: Start task " in s:
            self.in_active_task = True
        elif (
            "Scheduler: End task " in s
            or "Wait until " in s
            or "Server checker will retry" in s
        ):
            self.in_active_task = False

    def _drain_renderable_queue(self) -> None:
        """
        Drain all remaining logs from the IPC queue into renderables.
        Prevents race condition and message loss on process exit.
        """
        while True:
            try:
                log = self._renderable_queue.get_nowait()
                self.last_activity_time = time.time()
                self._update_task_state_from_log(log)
                self.renderables.append(log)
                if len(self.renderables) > self.renderables_max_length:
                    self.renderables = self.renderables[self.renderables_reduce_length :]
            except (queue.Empty, Exception):
                break

    def _thread_log_queue_handler(self) -> None:
        while self.alive:
            try:
                log = self._renderable_queue.get(timeout=1)
            except queue.Empty:
                continue
            self.last_activity_time = time.time()
            self._update_task_state_from_log(log)
            self.renderables.append(log)
            if len(self.renderables) > self.renderables_max_length:
                self.renderables = self.renderables[self.renderables_reduce_length :]
        self._drain_renderable_queue()
        logger.info("End of log queue handler loop")

    def _thread_watchdog(self) -> None:
        logger.info(f"[{self.config_name}] Subprocess watchdog thread started")
        while not self._watchdog_stop_event.wait(5):
            now = time.time()

            # 1. Main process low-frequency working set trimming (BLOCKER-2, D-07)
            if now - self.last_main_process_trim_time >= 1800:
                if not self.in_active_task:
                    try:
                        from module.base.memory_utils import empty_working_set
                        empty_working_set()
                    except Exception as e:
                        logger.debug(f"Main process working set trimming failed: {e}")
                    self.last_main_process_trim_time = now

            # 2. Watchdog hang detection in active tasks (BLOCKER-1, D-11)
            if self.alive:
                if self.in_active_task:
                    if now - self.last_activity_time > 180:
                        logger.warning(
                            f"[{self.config_name}] Subprocess unresponsive for >180s in active task, forcing watchdog kill"
                        )
                        try:
                            self._process.kill()
                        except Exception as e:
                            logger.error(f"Failed to kill unresponsive subprocess: {e}")
                        self.renderables.append(
                            f"[{self.config_name}] exited. Reason: Watchdog kill\n"
                        )
                        self._drain_renderable_queue()
                        time.sleep(0.5)
                        if not self._watchdog_stop_event.is_set():
                            logger.info(f"[{self.config_name}] Restarting after watchdog kill")
                            self.start(func=get_config_mod(self.config_name), ev=self.ev)
                else:
                    # In wait_until or maintenance wait, hang detection is suspended
                    self.last_activity_time = now
            else:
                # 3. Safe restart recycling detection (D-10, WARNING-1)
                if not self._watchdog_stop_event.is_set():
                    self._drain_renderable_queue()
                    if len(self.renderables) > 0:
                        last_log = self._renderable_to_str(self.renderables[-1]).strip()
                        if "Reason: Safe restart" in last_log:
                            logger.info(f"[{self.config_name}] Safe restart requested, recycling worker process")
                            time.sleep(0.5)
                            if not self._watchdog_stop_event.is_set():
                                self.start(func=get_config_mod(self.config_name), ev=self.ev)
        logger.info(f"[{self.config_name}] Subprocess watchdog thread stopped")

    @property
    def alive(self) -> bool:
        if self._process is not None:
            return self._process.is_alive()
        else:
            return False

    @property
    def state(self) -> int:
        if self.alive:
            return 1
        elif len(self.renderables) == 0:
            return 2
        else:
            s = self._renderable_to_str(self.renderables[-1]).strip()
            if s.endswith("Reason: Manual stop"):
                return 2
            elif s.endswith("Reason: Finish"):
                return 2
            elif s.endswith("Reason: Update"):
                return 4
            elif "Reason: Safe restart" in s:
                return 1
            else:
                return 3

    @classmethod
    def get_manager(cls, config_name: str) -> "ProcessManager":
        """
        Create a new alas if not exists.
        """
        if config_name not in cls._processes:
            cls._processes[config_name] = ProcessManager(config_name)
        return cls._processes[config_name]

    @staticmethod
    def run_process(
        config_name, func: str, q: queue.Queue, e: threading.Event = None
    ) -> None:
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--electron", action="store_true", help="Runs by electron client."
        )
        args, _ = parser.parse_known_args()
        State.electron = args.electron

        # Setup logger
        set_file_logger(name=config_name)
        if State.electron:
            # https://github.com/LmeSzinc/AzurLaneAutoScript/issues/2051
            logger.info("Electron detected, remove log output to stdout")
            from module.logger import console_hdlr
            logger.removeHandler(console_hdlr)
        set_func_logger(func=q.put)

        from module.config.config import AzurLaneConfig

        # Remove fake PIL module, because subprocess will use it
        remove_fake_pil_module()

        AzurLaneConfig.stop_event = e
        try:
            # Run alas
            if func == "alas":
                from alas import AzurLaneAutoScript

                if e is not None:
                    AzurLaneAutoScript.stop_event = e
                AzurLaneAutoScript(config_name=config_name).loop()
            elif func in get_available_func():
                from alas import AzurLaneAutoScript

                AzurLaneAutoScript(config_name=config_name).run(inflection.underscore(func), skip_first_screenshot=True)
            elif func in get_available_mod():
                mod = load_mod(func)

                if e is not None:
                    mod.set_stop_event(e)
                mod.loop(config_name)
            elif func in get_available_mod_func():
                getattr(load_mod(get_func_mod(func)), inflection.underscore(func))(config_name)
            else:
                logger.critical(f"No function matched: {func}")
            logger.info(f"[{config_name}] exited. Reason: Finish\n")
        except Exception as e:
            logger.exception(e)

    @classmethod
    def running_instances(cls) -> List["ProcessManager"]:
        l = []
        for process in cls._processes.values():
            if process.alive:
                l.append(process)
        return l

    @staticmethod
    def restart_processes(
        instances: List[Union["ProcessManager", str]] = None, ev: threading.Event = None
    ):
        """
        After update and reload, or failed to perform an update,
        restart all alas that running before update
        """
        logger.hr("Restart alas")

        # Load MOD_CONFIG_DICT
        list_mod_instance()

        if instances is None:
            instances = []

        _instances = set()

        for instance in instances:
            if isinstance(instance, str):
                _instances.add(ProcessManager.get_manager(instance))
            elif isinstance(instance, ProcessManager):
                _instances.add(instance)

        try:
            with open("./config/reloadalas", mode="r") as f:
                for line in f.readlines():
                    line = line.strip()
                    _instances.add(ProcessManager.get_manager(line))
        except FileNotFoundError:
            pass

        for process in _instances:
            logger.info(f"Starting [{process.config_name}]")
            process.start(func=get_config_mod(process.config_name), ev=ev)

        try:
            os.remove("./config/reloadalas")
        except:
            pass
        logger.info("Start alas complete")
