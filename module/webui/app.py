import argparse
import json
import queue
import threading
import time
from datetime import datetime
from functools import partial
from typing import Dict, List, Optional

# Import fake module before import pywebio to avoid importing unnecessary module PIL
from module.webui.fake_pil_module import import_fake_pil_module

import_fake_pil_module()

from pywebio import config as webconfig
from pywebio.input import file_upload, input, input_group, select
from pywebio.output import (
    Output,
    clear,
    close_popup,
    popup,
    put_button,
    put_buttons,
    put_collapse,
    put_column,
    put_error,
    put_html,
    put_link,
    put_loading,
    put_markdown,
    put_row,
    put_scope,
    put_table,
    put_text,
    put_warning,
    toast,
    use_scope,
)
from pywebio.pin import pin, pin_on_change
from pywebio.session import download, go_app, info, local, register_thread, run_js, set_env

import module.webui.lang as lang
from module.config.config import AzurLaneConfig, Function
from module.config.deep import deep_get, deep_iter, deep_set
from module.config.env import IS_ON_PHONE_CLOUD
from module.config.server import to_server
from module.config.utils import (
    alas_instance,
    alas_template,
    dict_to_kv,
    filepath_args,
    filepath_config,
    read_file,
)
from module.logger import logger
from module.ocr.rpc import start_ocr_server_process, stop_ocr_server_process
from module.submodule.submodule import load_config
from module.submodule.utils import get_config_mod
from module.webui.base import Frame
from module.webui.discord_presence import close_discord_rpc, init_discord_rpc
from module.webui.fastapi import asgi_app
from module.webui.lang import _t, t
from module.webui.patch import fix_py37_subprocess_communicate, patch_executor, patch_mimetype
from module.webui.pin import put_input, put_select
from module.webui.process_manager import ProcessManager
from module.webui.remote_access import RemoteAccess
from module.webui.setting import State
from module.webui.updater import updater
from module.webui.utils import (
    Icon,
    Switch,
    TaskHandler,
    add_css,
    filepath_css,
    get_alas_config_listen_path,
    get_localstorage,
    get_window_visibility_state,
    login,
    parse_pin_value,
    raise_exception,
    re_fullmatch,
    to_pin_value,
)
from module.webui.widgets import (
    BinarySwitchButton,
    RichLog,
    T_Output_Kwargs,
    put_icon_buttons,
    put_loading_text,
    put_none,
    put_output,
)

patch_executor()
patch_mimetype()
fix_py37_subprocess_communicate()
task_handler = TaskHandler()


class AlasGUI(Frame):
    ALAS_MENU: Dict[str, Dict[str, List[str]]]
    ALAS_ARGS: Dict[str, Dict[str, Dict[str, Dict[str, str]]]]
    theme = "default"

    def initial(self) -> None:
        self.ALAS_MENU = read_file(filepath_args("menu", self.alas_mod))
        self.ALAS_ARGS = read_file(filepath_args("args", self.alas_mod))
        self._init_alas_config_watcher()

    def __init__(self) -> None:
        super().__init__()
        # modified keys, return values of pin_wait_change()
        self.modified_config_queue = queue.Queue()
        # alas config name
        self.alas_name = ""
        self.alas_mod = "alas"
        self.alas_config = AzurLaneConfig("template")
        self.initial()
        # rendered state cache
        self.rendered_cache = []
        self.inst_cache = []
        self.load_home = False
        self.af_flag = False

    @use_scope("aside", clear=True)
    def set_aside(self) -> None:
        # TODO: update put_icon_buttons()

        current_date = datetime.now().date()
        if current_date.month == 4 and current_date.day == 1:
            self.af_flag = True

        put_icon_buttons(
            Icon.DEVELOP,
            buttons=[{"label": t("Gui.Aside.Home"), "value": "Home", "color": "aside"}],
            onclick=[self.ui_develop],
        )
        put_scope("aside_instance", [
            put_scope(f"alas-instance-{i}", [])
            for i, _ in enumerate(alas_instance())
        ])
        self.set_aside_status()
        put_icon_buttons(
            Icon.SETTING,
            buttons=[
                {
                    "label": t("Gui.AddAlas.Manage"),
                    "value": "AddAlas",
                    "color": "aside",
                }
            ],
            onclick=[lambda: go_app("manage", new_window=False)],
        )


    @use_scope("aside_instance")
    def set_aside_status(self) -> None:
        flag = True

        def update(name, seq):
            with use_scope(f"alas-instance-{seq}", clear=True):
                icon_html = Icon.RUN
                rendered_state = ProcessManager.get_manager(inst).state
                if rendered_state == 1 and self.af_flag:
                    icon_html = icon_html[:31] + ' anim-rotate' + icon_html[31:]
                put_icon_buttons(
                    icon_html,
                    buttons=[{"label": name, "value": name, "color": "aside"}],
                    onclick=self.ui_alas,
                )
            return rendered_state

        if not len(self.rendered_cache) or self.load_home:
            # Reload when add/delete new instance | first start app.py | go to HomePage (HomePage load call force reload)
            flag = False
            self.inst_cache.clear()
            self.inst_cache = alas_instance()
        if flag:
            for index, inst in enumerate(self.inst_cache):
                # Check for state change
                state = ProcessManager.get_manager(inst).state
                if state != self.rendered_cache[index]:
                    self.rendered_cache[index] = update(inst, index)
                    flag = False
        else:
            self.rendered_cache.clear()
            clear("aside_instance")
            for index, inst in enumerate(self.inst_cache):
                self.rendered_cache.append(update(inst, index))
            self.load_home = False
        if not flag:
            # Redraw lost focus, now focus on aside button
            aside_name = get_localstorage("aside")
            self.active_button("aside", aside_name)

        return

    @use_scope("header_status")
    def set_status(self, state: int) -> None:
        """
        Args:
            state (int):
                1 (running)
                2 (not running)
                3 (warning, stop unexpectedly)
                4 (stop for update)
                0 (hide)
                -1 (*state not changed)
        """
        if state == -1:
            return
        clear()

        if state == 1:
            put_loading_text(t("Gui.Status.Running"), color="success")
        elif state == 2:
            put_loading_text(t("Gui.Status.Inactive"), color="secondary", fill=True)
        elif state == 3:
            put_loading_text(t("Gui.Status.Warning"), shape="grow", color="warning")
        elif state == 4:
            put_loading_text(t("Gui.Status.Updating"), shape="grow", color="success")

    @classmethod
    def set_theme(cls, theme="default") -> None:
        cls.theme = theme
        State.deploy_config.Theme = theme
        State.theme = theme
        webconfig(theme=theme)

    @use_scope("menu", clear=True)
    def alas_set_menu(self) -> None:
        """
        Set menu
        """
        put_row(
            [
                put_buttons(
                    [
                        {
                            "label": t("Gui.MenuAlas.Overview"),
                            "value": "Overview",
                            "color": "menu",
                        }
                    ],
                    onclick=[self.alas_overview],
                ).style(f"--menu-Overview--"),
                put_button(
                    label="«",
                    onclick=self.toggle_menu,
                    color="menu",
                ).style("width: 2.2rem; padding: 0.25rem 0; margin-left: auto; text-align: center; border-radius: 4px; font-size: 0.95rem;").style("--btn-menu-collapse--"),
            ],
            size="1fr auto",
        )

        for menu, task_data in self.ALAS_MENU.items():
            if task_data.get("page") == "tool":
                _onclick = self.alas_daemon_overview
            else:
                _onclick = self.alas_set_group

            if task_data.get("menu") == "collapse":
                task_btn_list = [
                    put_buttons(
                        [
                            {
                                "label": t(f"Task.{task}.name"),
                                "value": task,
                                "color": "menu",
                            }
                        ],
                        onclick=_onclick,
                    ).style(f"--menu-{task}--")
                    for task in task_data.get("tasks", [])
                ]
                put_collapse(title=t(f"Menu.{menu}.name"), content=task_btn_list)
            else:
                title = t(f"Menu.{menu}.name")
                put_html(
                    '<div class="hr-task-group-box">'
                    '<span class="hr-task-group-line"></span>'
                    f'<span class="hr-task-group-text">{title}</span>'
                    '<span class="hr-task-group-line"></span>'
                    '</div>'
                )
                for task in task_data.get("tasks", []):
                    put_buttons(
                        [
                            {
                                "label": t(f"Task.{task}.name"),
                                "value": task,
                                "color": "menu",
                            }
                        ],
                        onclick=_onclick,
                    ).style(f"--menu-{task}--").style(f"padding-left: 0.75rem")

        self.alas_overview()

    @use_scope("content", clear=True)
    def alas_set_group(self, task: str) -> None:
        """
        Set arg groups from dict
        """
        self.init_menu(name=task)
        self.set_title(t(f"Task.{task}.name"))

        put_scope("_groups", [put_none(), put_scope("groups"), put_scope("navigator")])

        task_help: str = t(f"Task.{task}.help")
        if task_help:
            put_scope(
                "group__info",
                scope="groups",
                content=[put_text(task_help).style("font-size: 1rem")],
            )

        config = self.alas_config.read_file(self.alas_name)
        for group, arg_dict in deep_iter(self.ALAS_ARGS[task], depth=1):
            if self.set_group(group, arg_dict, config, task):
                self.set_navigator(group)

    @use_scope("groups")
    def set_group(self, group, arg_dict, config, task):
        group_name = group[0]
        server = to_server(deep_get(config, "Alas.Emulator.PackageName", "cn"))

        output_list: List[Output] = []
        for arg, arg_dict in deep_iter(arg_dict, depth=1):
            output_kwargs: T_Output_Kwargs = arg_dict.copy()

            # Skip hide
            display: Optional[str] = output_kwargs.pop("display", None)
            if display == "hide":
                continue
            # Disable
            elif display == "disabled":
                output_kwargs["disabled"] = True
            # Output type
            output_kwargs["widget_type"] = output_kwargs.pop("type")

            arg_name = arg[0]  # [arg_name,]
            # Internal pin widget name
            output_kwargs["name"] = f"{task}_{group_name}_{arg_name}"
            # Display title
            output_kwargs["title"] = t(f"{group_name}.{arg_name}.name")

            # Get value from config
            value = deep_get(
                config, [task, group_name, arg_name], output_kwargs["value"]
            )
            # idk
            value = str(value) if isinstance(value, datetime) else value
            # Default value
            output_kwargs["value"] = value
            # Options
            options = output_kwargs.pop("option", [])
            server_options = output_kwargs.get(f"option_{server}")
            if output_kwargs["widget_type"] == "select" and isinstance(server_options, list) and server_options:
                options = server_options
            output_kwargs["options"] = options
            if (
                task == "GemsFarming"
                and group_name == "Campaign"
                and arg_name == "Event"
                and output_kwargs["widget_type"] == "select"
                and len(options) == 1
            ):
                continue
            if output_kwargs["widget_type"] == "select" and len(options) == 1:
                only_option = options[0]
                if only_option in output_kwargs.get("option_bold", []):
                    output_kwargs["widget_type"] = "state"
            # Options label
            options_label = []
            for opt in options:
                options_label.append(t(f"{group_name}.{arg_name}.{opt}"))
            output_kwargs["options_label"] = options_label
            # Help
            arg_help = t(f"{group_name}.{arg_name}.help")
            if arg_help == "" or not arg_help:
                arg_help = None
            output_kwargs["help"] = arg_help
            # Invalid feedback
            output_kwargs["invalid_feedback"] = t("Gui.Text.InvalidFeedBack", value)

            o = put_output(output_kwargs)
            if o is not None:
                # output will inherit current scope when created, override here
                o.spec["scope"] = f"#pywebio-scope-group_{group_name}"
                output_list.append(o)

        if not output_list:
            return 0

        with use_scope(f"group_{group_name}"):
            put_text(t(f"{group_name}._info.name"))
            group_help = t(f"{group_name}._info.help")
            if group_help != "":
                put_text(group_help)
            put_html('<hr class="hr-group">')
            for output in output_list:
                output.show()

        return len(output_list)

    @use_scope("navigator")
    def set_navigator(self, group):
        js = f"""
            $("#pywebio-scope-groups").scrollTop(
                $("#pywebio-scope-group_{group[0]}").position().top
                + $("#pywebio-scope-groups").scrollTop() - 59
            )
        """
        put_button(
            label=t(f"{group[0]}._info.name"),
            onclick=lambda: run_js(js),
            color="navigator",
        )

    def alas_task_run_now(self, command: str) -> None:
        try:
            config = self.alas_config.read_file(self.alas_name)
            now = datetime.now().replace(microsecond=0)
            deep_set(config, f"{command}.Scheduler.NextRun", now)
            deep_set(config, f"{command}.Scheduler.Enable", True)
            self.alas_config.write_file(self.alas_name, config)
            task_name = t(f"Task.{command}.name")
            toast(f"【{task_name}】{t('Gui.Overview.RunNowSuccess')}", duration=1.5, color="success")
            self.alas_update_overview_task()
        except Exception as e:
            logger.exception(e)
            toast(str(e), duration=2, color="error")

    def alas_task_toggle_enable(self, command: str, enable: bool) -> None:
        try:
            config = self.alas_config.read_file(self.alas_name)
            deep_set(config, f"{command}.Scheduler.Enable", enable)
            self.alas_config.write_file(self.alas_name, config)
            status_text = t("Gui.Overview.Enabled") if enable else t("Gui.Overview.Disabled")
            task_name = t(f"Task.{command}.name")
            toast(f"【{task_name}】{status_text}", duration=1.5, color="info")
            self.alas_update_overview_task()
        except Exception as e:
            logger.exception(e)
            toast(str(e), duration=2, color="error")

    def alas_get_favorites(self) -> List[str]:
        config = self.alas_config.read_file(self.alas_name)
        favs = deep_get(config, "Alas.Storage.Storage.Favorites", default=[])
        return [f for f in favs if isinstance(f, str)] if isinstance(favs, list) else []

    def alas_toggle_favorite(self, command: str) -> None:
        try:
            config = self.alas_config.read_file(self.alas_name)
            favs = deep_get(config, "Alas.Storage.Storage.Favorites", default=[])
            if not isinstance(favs, list):
                favs = []
            favs = [f for f in favs if isinstance(f, str)]
            task_name = t(f"Task.{command}.name")
            if command in favs:
                favs.remove(command)
                toast(f"已取消收藏【{task_name}】", duration=1.5, color="info")
            else:
                favs.append(command)
                toast(f"已收藏【{task_name}】", duration=1.5, color="success")
            deep_set(config, "Alas.Storage.Storage.Favorites", favs)
            self.alas_config.write_file(self.alas_name, config)
            self.alas_update_overview_task()
        except Exception as e:
            logger.exception(e)
            toast(str(e), duration=2, color="error")

    def alas_popup_add_favorite(self) -> None:
        current_favs = set(self.alas_get_favorites())
        options = []
        for menu, task_data in self.ALAS_MENU.items():
            menu_name = t(f"Menu.{menu}.name")
            for task in task_data.get("tasks", []):
                if task.lower() in ["alas", "template", "restart"] or task in current_favs:
                    continue
                task_name = t(f"Task.{task}.name")
                options.append({"label": f"{task_name} ({menu_name})", "value": task})

        if not options:
            toast("所有可用任务已全部收藏！", duration=2, color="info")
            return

        def on_confirm():
            selected = pin.popup_add_favorite_select
            close_popup()
            if selected:
                self.alas_toggle_favorite(selected)

        popup(
            title=t("Gui.Button.AddFavorite"),
            content=[
                put_text("选择要加入收藏的任务："),
                put_select("popup_add_favorite_select", options=options),
                put_row(
                    [
                        put_button(t("Gui.AddAlas.Confirm"), onclick=on_confirm, color="success"),
                        put_button(t("Gui.AppManage.Back"), onclick=close_popup, color="secondary"),
                    ],
                    size="auto auto",
                ).style("margin-top: 1rem; gap: 8px; justify-content: flex-end;"),
            ],
        )

    def toggle_logs(self) -> None:
        collapse_text = t("Gui.Button.CollapseLog")
        expand_text = t("Gui.Button.ExpandLog")
        run_js(
            f"""
            var $ov = $("#pywebio-scope-overview");
            if ($ov.hasClass("logs-collapsed")) {{
                $ov.removeClass("logs-collapsed");
                localStorage.setItem("alas_logs_collapsed", "false");
                $("div[style*='--btn-toggle-log--']>button, div[style*='--btn-toggle-log-right--']>button").text('{collapse_text}');
            }} else {{
                $ov.addClass("logs-collapsed");
                localStorage.setItem("alas_logs_collapsed", "true");
                $("div[style*='--btn-toggle-log--']>button, div[style*='--btn-toggle-log-right--']>button").text('{expand_text}');
            }}
            """
        )

    @use_scope("content", clear=True)
    def alas_overview(self) -> None:
        self.init_menu(name="Overview")
        self.set_title(t(f"Gui.MenuAlas.Overview"))

        put_scope("overview", [put_scope("schedulers"), put_scope("logs")])

        with use_scope("schedulers"):
            put_scope(
                "scheduler-bar",
                [
                    put_button(
                        label="»",
                        onclick=self.toggle_menu,
                        color="menu",
                    ).style("width: 2.2rem; padding: 0.25rem 0; margin: auto 0.5rem auto 0; text-align: center; border-radius: 4px; font-size: 0.95rem;").style("--btn-menu-expand--"),
                    put_text(t("Gui.Overview.Scheduler")).style(
                        "font-size: 1.25rem; font-weight: 600; margin: auto .5rem auto 0;"
                    ),
                    put_row(
                        [
                            put_scope("scheduler_btn"),
                            put_button(
                                label=t("Gui.Button.CollapseLog"),
                                onclick=self.toggle_logs,
                                color="off",
                            ).style("padding: .22rem .65rem; font-size: .85rem; border-radius: 4px; margin-left: 0.4rem;").style("--btn-toggle-log--"),
                        ],
                        size="auto auto",
                    ).style("margin: auto 0 auto auto; align-items: center;"),
                ],
            )
            put_scope(
                "running",
                [
                    put_text(t("Gui.Overview.Running")).style("--section-title--"),
                    put_scope("running_tasks"),
                ],
            )
            put_scope(
                "pending",
                [
                    put_text(t("Gui.Overview.QueueTitle")).style("--section-title--"),
                    put_scope("pending_tasks"),
                ],
            )
            put_scope(
                "favorites",
                [
                    put_collapse(
                        title=t("Gui.Overview.Favorites"),
                        content=[
                            put_row(
                                [
                                    put_button(
                                        label=t("Gui.Button.AddFavorite"),
                                        onclick=self.alas_popup_add_favorite,
                                        color="off",
                                    ).style("margin: 0 0 0.4rem auto; padding: .2rem .6rem; font-size: .82rem; border-radius: 4px;"),
                                ],
                                size="1fr",
                            ).style("align-items: center;"),
                            put_scope("favorite_tasks"),
                        ],
                        open=False,
                    )
                ],
            )
            put_scope(
                "waiting",
                [
                    put_collapse(
                        title=t("Gui.Overview.Waiting"),
                        content=[put_scope("waiting_tasks")],
                        open=False,
                    )
                ],
            )
            put_scope(
                "disabled",
                [
                    put_collapse(
                        title=t("Gui.Overview.Disabled"),
                        content=[put_scope("disabled_tasks")],
                        open=False,
                    )
                ],
            )

        def update_scheduler_btn(label, onclick, color):
            clear("scheduler_btn")
            put_button(
                label=label,
                onclick=onclick,
                color=color,
                scope="scheduler_btn",
            ).style("padding: .22rem .8rem; font-size: .85rem; border-radius: 4px; font-weight: 500;")

            is_alive = (label == t("Gui.Button.Stop"))
            status_text = t("Gui.Overview.StatusRunning") if is_alive else t("Gui.Overview.StatusIdle")
            dot_class = "status-dot status-dot-running" if is_alive else "status-dot status-dot-idle"
            badge_class = "scheduler-status-badge status-running" if is_alive else "scheduler-status-badge status-idle"
            run_js(f"""
            $("#scheduler-status-indicator").attr("class", "{badge_class}").html('<span class="{dot_class}"></span><span class="status-text">{status_text}</span>');
            """)

        switch_scheduler = BinarySwitchButton(
            label_on=t("Gui.Button.Stop"),
            label_off=t("Gui.Button.Start"),
            onclick_on=lambda: self.alas.stop(),
            onclick_off=lambda: self.alas.start(None, updater.event),
            get_state=lambda: self.alas.alive,
            color_on="danger",
            color_off="success",
            scope="scheduler_btn",
        )
        switch_scheduler.update_button = update_scheduler_btn

        log = RichLog("log")

        with use_scope("logs"):
            put_scope(
                "log-bar",
                [
                    put_text(t("Gui.Overview.Log")).style(
                        "font-size: 1.25rem; margin: auto .5rem auto;"
                    ),
                    put_scope(
                        "log-bar-btns",
                        [
                            put_scope("log_scroll_btn"),
                            put_button(
                                label=t("Gui.Button.CollapseLog"),
                                onclick=self.toggle_logs,
                                color="off",
                            ).style("padding: .22rem .65rem; font-size: .85rem; border-radius: 4px; margin-left: 0.4rem;").style("--btn-toggle-log-right--"),
                        ],
                    ),
                ],
            )
            put_scope("log", [put_html("")])

        log.console.width = log.get_width()

        switch_log_scroll = BinarySwitchButton(
            label_on=t("Gui.Button.ScrollON"),
            label_off=t("Gui.Button.ScrollOFF"),
            onclick_on=lambda: log.set_scroll(False),
            onclick_off=lambda: log.set_scroll(True),
            get_state=lambda: log.keep_bottom,
            color_on="on",
            color_off="off",
            scope="log_scroll_btn",
        )

        self.task_handler.add(switch_scheduler.g(), 1, True)
        self.task_handler.add(switch_log_scroll.g(), 1, True)
        self.task_handler.add(self.alas_update_overview_task, 10, True)
        self.task_handler.add(log.put_log(self.alas), 0.25, True)

        collapse_text = t("Gui.Button.CollapseLog")
        expand_text = t("Gui.Button.ExpandLog")
        run_js(
            f"""
            localStorage.removeItem("alas_menu_collapsed");
            if (localStorage.getItem("alas_logs_collapsed") === "true") {{
                $("#pywebio-scope-overview").addClass("logs-collapsed");
                $("div[style*='--btn-toggle-log--']>button, div[style*='--btn-toggle-log-right--']>button").text('{expand_text}');
            }} else {{
                $("div[style*='--btn-toggle-log--']>button, div[style*='--btn-toggle-log-right--']>button").text('{collapse_text}');
            }}
            if (window.innerWidth > 768 && localStorage.getItem("alas_menu_collapsed_pc") === "true") {{
                $("#pywebio-scope-menu").addClass("menu-collapsed-pc");
            }} else {{
                $("#pywebio-scope-menu").removeClass("menu-collapsed-pc");
            }}
            if (window.purgeAlasDisclaimers) {{
                window.purgeAlasDisclaimers();
            }}
            """
        )

    def _init_alas_config_watcher(self) -> None:
        def put_queue(path, value):
            self.modified_config_queue.put({"name": path, "value": value})

        for path in get_alas_config_listen_path(self.ALAS_ARGS):
            pin_on_change(
                name="_".join(path), onchange=partial(put_queue, ".".join(path))
            )
        logger.info("Init config watcher done.")

    def _alas_thread_update_config(self) -> None:
        modified = {}
        while self.alive:
            try:
                d = self.modified_config_queue.get(timeout=10)
                config_name = self.alas_name
                config_updater = self.alas_config
            except queue.Empty:
                continue
            modified[d["name"]] = d["value"]
            while True:
                try:
                    d = self.modified_config_queue.get(timeout=1)
                    modified[d["name"]] = d["value"]
                except queue.Empty:
                    self._save_config(modified, config_name, config_updater)
                    modified.clear()
                    break

    def _save_config(
            self,
            modified: Dict[str, str],
            config_name: str,
            config_updater: AzurLaneConfig = State.config_updater,
    ) -> None:
        try:
            valid = []
            invalid = []
            config = config_updater.read_file(config_name)
            n = datetime.now()
            for p, v in deep_iter(config, depth=3):
                if p[-1].endswith('un') and not isinstance(v, bool):
                    if (v - n).days >= 31:
                        deep_set(config, p, '')
            for k, v in modified.copy().items():
                valuetype = deep_get(self.ALAS_ARGS, k + ".valuetype")
                v = parse_pin_value(v, valuetype)
                validate = deep_get(self.ALAS_ARGS, k + ".validate")
                if not len(str(v)):
                    default = deep_get(self.ALAS_ARGS, k + ".value")
                    modified[k] = default
                    deep_set(config, k, default)
                    valid.append(k)
                    pin["_".join(k.split("."))] = default

                elif not validate or re_fullmatch(validate, v):
                    deep_set(config, k, v)
                    modified[k] = v
                    valid.append(k)
                    for set_key, set_value in config_updater.save_callback(k, v):
                        modified[set_key] = set_value
                        deep_set(config, set_key, set_value)
                        valid.append(set_key)
                        pin["_".join(set_key.split("."))] = to_pin_value(set_value)
                else:
                    modified.pop(k)
                    invalid.append(k)
                    logger.warning(f"Invalid value {v} for key {k}, skip saving.")
            self.pin_remove_invalid_mark(valid)
            self.pin_set_invalid_mark(invalid)
            if modified:
                toast(
                    t("Gui.Toast.ConfigSaved"),
                    duration=1,
                    position="right",
                    color="success",
                )
                logger.info(
                    f"Save config {filepath_config(config_name)}, {dict_to_kv(modified)}"
                )
                config_updater.write_file(config_name, config)
        except Exception as e:
            logger.exception(e)

    def alas_update_overview_task(self) -> None:
        if not self.visible:
            return
        self.alas_config.load()
        self.alas_config.get_next_task()

        if len(self.alas_config.pending_task) >= 1:
            if self.alas.alive:
                running = self.alas_config.pending_task[:1]
                pending = self.alas_config.pending_task[1:]
            else:
                running = []
                pending = self.alas_config.pending_task[:]
        else:
            running = []
            pending = []
        waiting = self.alas_config.waiting_task
        disabled = getattr(self.alas_config, "disabled_task", [])
        fav_commands = self.alas_get_favorites()

        def put_task(func: Function, status: str = "normal", is_favorite: bool = False, prefix: str = ""):
            with use_scope(f"overview-task_{prefix}_{func.command}"):
                if status == "running":
                    time_icon = "⚡ "
                    time_str = t("Gui.Overview.Running")
                elif status == "pending":
                    time_icon = "⏳ "
                    time_str = t("Gui.Overview.Pending")
                elif status == "disabled":
                    time_icon = "⛔ "
                    time_str = t("Gui.Overview.Disabled")
                else:
                    time_icon = "🕒 "
                    time_str = str(func.next_run)

                task_name = t(f"Task.{func.command}.name")
                put_column(
                    [
                        put_text(task_name).style("--arg-title--"),
                        put_text(f"{time_icon}{time_str}").style("--arg-help--"),
                    ],
                    size="auto auto",
                )

                btns = []
                if status in ("waiting", "pending"):
                    btns.append(
                        put_button(
                            label=t("Gui.Button.RunNow"),
                            onclick=partial(self.alas_task_run_now, func.command),
                            color="success",
                        ).style("background-color: #2ea043; border-color: #2ea043;")
                    )
                    btns.append(
                        put_button(
                            label=t("Gui.Button.Disable"),
                            onclick=partial(self.alas_task_toggle_enable, func.command, False),
                            color="danger",
                        ).style("background-color: #da3633; border-color: #da3633;")
                    )
                elif status == "disabled":
                    btns.append(
                        put_button(
                            label=t("Gui.Button.Enable"),
                            onclick=partial(self.alas_task_toggle_enable, func.command, True),
                            color="primary",
                        ).style("background-color: #1f6feb; border-color: #1f6feb;")
                    )
                btns.append(
                    put_button(
                        label=t("Gui.Button.Setting"),
                        onclick=partial(self.alas_set_group, func.command),
                        color="off",
                    )
                )
                fav_label = "★" if is_favorite else "☆"
                fav_color = "warning" if is_favorite else "off"
                btns.append(
                    put_button(
                        label=fav_label,
                        onclick=partial(self.alas_toggle_favorite, func.command),
                        color=fav_color,
                    ).style("font-size: 0.95rem; line-height: 1;")
                )
                put_row(btns, size=" ".join(["auto"] * len(btns))).style("margin: auto 0 auto auto; gap: 4px; align-items: center;")

        clear("running_tasks")
        clear("favorite_tasks")
        clear("pending_tasks")
        clear("waiting_tasks")
        clear("disabled_tasks")

        with use_scope("running_tasks"):
            if running:
                for task in running:
                    put_task(task, status="running", is_favorite=(task.command in fav_commands), prefix="run")
            else:
                put_text(t("Gui.Overview.NoTask")).style("--overview-notask-text--")

        with use_scope("favorite_tasks"):
            if fav_commands:
                for cmd in fav_commands:
                    raw_data = self.alas_config.data.get(cmd, {})
                    func = Function(raw_data)
                    func.command = cmd
                    if running and running[0].command == cmd:
                        status = "running"
                        func.next_run = running[0].next_run
                    elif any(p.command == cmd for p in pending):
                        status = "pending"
                        p_task = next(p for p in pending if p.command == cmd)
                        func.next_run = p_task.next_run
                    elif any(w.command == cmd for w in waiting):
                        status = "waiting"
                        w_task = next(w for w in waiting if w.command == cmd)
                        func.next_run = w_task.next_run
                    else:
                        status = "disabled"
                    put_task(func, status=status, is_favorite=True, prefix="fav")
            else:
                put_text(t("Gui.Overview.NoFavorite")).style("--overview-notask-text--")

        with use_scope("pending_tasks"):
            if pending:
                for task in pending:
                    put_task(task, status="pending", is_favorite=(task.command in fav_commands), prefix="pen")
            else:
                put_text(t("Gui.Overview.NoTask")).style("--overview-notask-text--")

        with use_scope("waiting_tasks"):
            if waiting:
                for task in waiting:
                    put_task(task, status="waiting", is_favorite=(task.command in fav_commands), prefix="wait")
            else:
                put_text(t("Gui.Overview.NoTask")).style("--overview-notask-text--")

        with use_scope("disabled_tasks"):
            if disabled:
                for task in disabled:
                    put_task(task, status="disabled", is_favorite=(task.command in fav_commands), prefix="dis")
            else:
                put_text(t("Gui.Overview.NoTask")).style("--overview-notask-text--")

    @use_scope("content", clear=True)
    def alas_daemon_overview(self, task: str) -> None:
        self.init_menu(name=task)
        self.set_title(t(f"Task.{task}.name"))

        log = RichLog("log")

        if self.is_mobile:
            put_scope(
                "daemon-overview",
                [
                    put_scope("scheduler-bar"),
                    put_scope("groups"),
                    put_scope("log-bar"),
                    put_scope("log", [put_html("")]),
                ],
            )
        else:
            put_scope(
                "daemon-overview",
                [
                    put_none(),
                    put_scope(
                        "_daemon",
                        [
                            put_scope(
                                "_daemon_upper",
                                [put_scope("scheduler-bar"), put_scope("log-bar")],
                            ),
                            put_scope("groups"),
                            put_scope("log", [put_html("")]),
                        ],
                    ),
                    put_none(),
                ],
            )

        log.console.width = log.get_width()

        with use_scope("scheduler-bar"):
            put_button(
                label="»",
                onclick=self.toggle_menu,
                color="menu",
            ).style("width: 2.2rem; padding: 0.25rem 0; margin: auto 0.5rem auto 0; text-align: center; border-radius: 4px; font-size: 0.95rem;").style("--btn-menu-expand--"),
            put_text(t("Gui.Overview.Scheduler")).style(
                "font-size: 1.25rem; margin: auto .5rem auto;"
            )
            put_scope("scheduler_btn")

        switch_scheduler = BinarySwitchButton(
            label_on=t("Gui.Button.Stop"),
            label_off=t("Gui.Button.Start"),
            onclick_on=lambda: self.alas.stop(),
            onclick_off=lambda: self.alas.start(task),
            get_state=lambda: self.alas.alive,
            color_on="off",
            color_off="on",
            scope="scheduler_btn",
        )

        with use_scope("log-bar"):
            put_text(t("Gui.Overview.Log")).style(
                "font-size: 1.25rem; margin: auto .5rem auto;"
            )
            put_scope(
                "log-bar-btns",
                [
                    put_scope("log_scroll_btn"),
                ],
            )

        switch_log_scroll = BinarySwitchButton(
            label_on=t("Gui.Button.ScrollON"),
            label_off=t("Gui.Button.ScrollOFF"),
            onclick_on=lambda: log.set_scroll(False),
            onclick_off=lambda: log.set_scroll(True),
            get_state=lambda: log.keep_bottom,
            color_on="on",
            color_off="off",
            scope="log_scroll_btn",
        )

        config = self.alas_config.read_file(self.alas_name)
        for group, arg_dict in deep_iter(self.ALAS_ARGS[task], depth=1):
            if group[0] == "Storage":
                continue
            self.set_group(group, arg_dict, config, task)

        run_js(
            """
            $("#pywebio-scope-log").css(
                "grid-row-start",
                -2 - $("#pywebio-scope-_daemon").children().filter(
                    function(){
                        return $(this).css("display") === "none";
                    }
                ).length
            );
            $("#pywebio-scope-log").css(
                "grid-row-end",
                -1
            );
        """
        )

        self.task_handler.add(switch_scheduler.g(), 1, True)
        self.task_handler.add(switch_log_scroll.g(), 1, True)
        self.task_handler.add(log.put_log(self.alas), 0.25, True)

    @use_scope("menu", clear=True)
    def dev_set_menu(self) -> None:
        self.init_menu(collapse_menu=False, name="Develop")

        put_button(
            label=t("Gui.MenuDevelop.HomePage"),
            onclick=self.show,
            color="menu",
        ).style(f"--menu-HomePage--")

        # put_button(
        #     label=t("Gui.MenuDevelop.Translate"),
        #     onclick=self.dev_translate,
        #     color="menu",
        # ).style(f"--menu-Translate--")

        put_button(
            label=t("Gui.MenuDevelop.Update"),
            onclick=self.dev_update,
            color="menu",
        ).style(f"--menu-Update--")

        put_button(
            label=t("Gui.MenuDevelop.Remote"),
            onclick=self.dev_remote,
            color="menu",
        ).style(f"--menu-Remote--")

        put_button(
            label=t("Gui.MenuDevelop.Utils"),
            onclick=self.dev_utils,
            color="menu",
        ).style(f"--menu-Utils--")

    def dev_translate(self) -> None:
        go_app("translate", new_window=True)
        lang.TRANSLATE_MODE = True
        self.show()

    @use_scope("content", clear=True)
    def dev_update(self) -> None:
        self.init_menu(name="Update")
        self.set_title(t("Gui.MenuDevelop.Update"))

        if State.restart_event is None:
            put_warning(t("Gui.Update.DisabledWarn"))

        put_scope("updater_source")
        put_row(
            content=[put_scope("updater_loading"), None, put_scope("updater_state")],
            size="auto .25rem 1fr",
        )

        put_scope("updater_btn")
        put_scope("updater_info")
        put_scope("updater_detail")

        def get_custom_branch_from_pin():
            branch = None
            try:
                branch = pin['custom_branch_input']
            except Exception:
                pass
            if not branch:
                branch = getattr(updater, 'CustomBranch', 'custom') or 'custom'
            return branch.strip()

        def on_click_official_update():
            if updater.state in ("start", "wait", "run update"):
                toast("更新任务正在进行中，请稍候...", color="warning")
                return
            updater.switch_source("official")
            render_cards()
            toast("已切换为【官方更新源】(master 分支)，开始执行更新...", color="info")
            updater.state = 1
            updater.run_update()

        def on_click_official_check():
            if updater.state in ("start", "wait", "run update"):
                toast("更新任务正在进行中，请稍候...", color="warning")
                return
            updater.switch_source("official")
            render_cards()
            toast("已切换为【官方更新源】(master 分支)，正在检查更新...", color="info")
            updater.check_update()

        def on_click_custom_update():
            if updater.state in ("start", "wait", "run update"):
                toast("更新任务正在进行中，请稍候...", color="warning")
                return
            branch = get_custom_branch_from_pin()
            repo = getattr(updater, 'CustomRepository', None) or 'https://github.com/TwotwoPiggy/AzurLaneAutoScript'
            updater.switch_source("custom", custom_repo=repo, custom_branch=branch)
            render_cards()
            toast(f"已切换为【私有更新源】({branch} 分支)，开始执行更新...", color="success")
            updater.state = 1
            updater.run_update()

        def on_click_custom_check():
            if updater.state in ("start", "wait", "run update"):
                toast("更新任务正在进行中，请稍候...", color="warning")
                return
            branch = get_custom_branch_from_pin()
            repo = getattr(updater, 'CustomRepository', None) or 'https://github.com/TwotwoPiggy/AzurLaneAutoScript'
            updater.switch_source("custom", custom_repo=repo, custom_branch=branch)
            render_cards()
            toast(f"已切换为【私有更新源】({branch} 分支)，正在检查更新...", color="info")
            updater.check_update()

        def select_fast_branch(branch_name: str):
            try:
                pin['custom_branch_input'] = branch_name
            except Exception:
                pass
            repo = getattr(updater, 'CustomRepository', None) or 'https://github.com/TwotwoPiggy/AzurLaneAutoScript'
            updater.switch_source("custom", custom_repo=repo, custom_branch=branch_name)
            render_cards()
            toast(f"已切换至私有源 [{branch_name}] 分支", color="success")
            updater.check_update()

        def show_custom_repo_modal():
            def on_save():
                repo = None
                branch = None
                try:
                    repo = pin['modal_repo_url']
                except Exception:
                    pass
                try:
                    branch = pin['modal_repo_branch']
                except Exception:
                    pass
                repo = (repo or "").strip()
                branch = (branch or "custom").strip()
                if repo:
                    updater.switch_source("custom", custom_repo=repo, custom_branch=branch)
                    close_popup()
                    toast("个人仓库配置已保存并激活", color="success")
                    render_cards()
                    updater.check_update()

            popup("配置个人 GitHub 仓库", [
                put_text("请输入您的个人 GitHub 仓库地址与默认更新分支："),
                put_input('modal_repo_url', label='仓库地址', value=getattr(updater, 'CustomRepository', '') or 'https://github.com/TwotwoPiggy/AzurLaneAutoScript'),
                put_input('modal_repo_branch', label='默认分支', value=getattr(updater, 'CustomBranch', 'custom') or 'custom'),
                put_button("保存并切换", onclick=on_save, color="success")
            ])

        def render_cards():
            with use_scope("updater_source", clear=True):
                curr = getattr(updater, 'UpdateSource', 'custom')
                active_repo = updater.Repository
                active_branch = updater.Branch

                custom_repo = getattr(updater, 'CustomRepository', None) or 'https://github.com/TwotwoPiggy/AzurLaneAutoScript'
                custom_branch = getattr(updater, 'CustomBranch', 'custom') or 'custom'

                is_official = (curr == 'official')
                is_custom = (curr == 'custom')

                official_badge = '<span style="background: #1976d2; color: #fff; padding: 1px 6px; border-radius: 3px; font-size: 0.75em; margin-left: 6px;">当前激活</span>' if is_official else ''
                custom_badge = '<span style="background: #2e7d32; color: #fff; padding: 1px 6px; border-radius: 3px; font-size: 0.75em; margin-left: 6px;">当前激活</span>' if is_custom else ''

                # 顶部状态横幅
                put_html(f"""
                <div style="background: rgba(125,125,125,0.05); border: 1px solid rgba(125,125,125,0.2); border-radius: 6px; padding: 6px 12px; margin-bottom: 10px; font-size: 0.85em; line-height: 1.4;">
                    <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 6px;">
                        <div>
                            <span style="color: #666;">当前生效更新源：</span>
                            <span style="font-weight: bold; color: {'#1976d2' if is_official else '#2e7d32'};">
                                {'🏛️ 官方原版 (Official)' if is_official else '🌟 个人私有版 (Custom)'}
                            </span>
                            <span style="color: #999; margin: 0 6px;">|</span>
                            <span style="color: #666;">地址：<code>{active_repo}</code></span>
                            <span style="color: #999; margin: 0 6px;">|</span>
                            <span style="color: #666;">当前分支：<code style="font-weight:bold; color:#d32f2f;">{active_branch}</code></span>
                        </div>
                    </div>
                </div>
                """)

                # 左右双卡片外壳
                card_style_official = f"border: 1px solid {'#1976d2' if is_official else 'rgba(25,118,210,0.25)'}; border-radius: 8px; padding: 12px 14px; background: {'rgba(25,118,210,0.05)' if is_official else 'rgba(25,118,210,0.02)'}; height: fit-content;"
                card_style_custom = f"border: 1px solid {'#2e7d32' if is_custom else 'rgba(46,125,50,0.25)'}; border-radius: 8px; padding: 12px 14px; background: {'rgba(46,125,50,0.05)' if is_custom else 'rgba(46,125,50,0.02)'}; height: fit-content;"

                put_row([
                    put_scope("card_official").style(card_style_official),
                    None,
                    put_scope("card_custom").style(card_style_custom),
                ], size="1fr 12px 1fr").style("align-items: start;")

                # 填充官方卡片内容
                with use_scope("card_official", clear=True):
                    put_html(f"""
                    <div style="font-size: 1.05em; font-weight: bold; color: #1976d2; display: flex; align-items: center; margin-bottom: 6px;">
                        🏛️ 官方更新 (Official) {official_badge}
                    </div>
                    <div style="color: #666; font-size: 0.82em; word-break: break-all; margin-bottom: 2px;">
                        仓库：<code>https://github.com/LmeSzinc/AzurLaneAutoScript</code>
                    </div>
                    <div style="color: #666; font-size: 0.82em; margin-bottom: 4px;">
                        分支：<code>master</code> (官方稳定主线)
                    </div>
                    <div style="color: #888; font-size: 0.78em; margin-bottom: 8px;">
                        用于直接同步官方发布的最新主线改动。
                    </div>
                    """)
                    put_row([
                        put_button("🏛️ 官方更新", onclick=on_click_official_update, color="primary"),
                        None,
                        put_button("🔍 检查官方更新", onclick=on_click_official_check, color="info", outline=True),
                    ], size="auto 8px auto")

                # 填充私有卡片内容
                with use_scope("card_custom", clear=True):
                    put_html(f"""
                    <div style="font-size: 1.05em; font-weight: bold; color: #2e7d32; display: flex; align-items: center; margin-bottom: 6px;">
                        🌟 私有更新 (Custom) {custom_badge}
                    </div>
                    <div style="color: #666; font-size: 0.82em; word-break: break-all; margin-bottom: 2px;">
                        仓库：<code>{custom_repo}</code>
                    </div>
                    <div style="color: #888; font-size: 0.78em; margin-bottom: 8px;">
                        支持从个人 GitHub 仓库拉取并更新指定分支。
                    </div>
                    """)
                    put_row([
                        put_input('custom_branch_input', value=custom_branch, placeholder='更新分支: custom / master').style("margin-bottom: 0;"),
                        None,
                        put_button("⚙️ 仓库配置", onclick=show_custom_repo_modal, color="secondary", outline=True).style("white-space: nowrap;"),
                    ], size="1fr 8px auto").style("align-items: center; margin-bottom: 6px;")

                    put_row([
                        put_text("快捷分支:").style("font-size: 0.82em; color: #666; line-height: 24px; margin: 0; white-space: nowrap;"),
                        None,
                        put_button("custom", onclick=lambda: select_fast_branch("custom"), color="success", outline=True).style("padding: 2px 8px; font-size: 0.8em;"),
                        None,
                        put_button("master", onclick=lambda: select_fast_branch("master"), color="secondary", outline=True).style("padding: 2px 8px; font-size: 0.8em;"),
                    ], size="auto 6px auto 6px auto").style("align-items: center; margin-bottom: 8px;")

                    put_row([
                        put_button("🚀 私有更新", onclick=on_click_custom_update, color="success"),
                        None,
                        put_button("🔍 检查私有更新", onclick=on_click_custom_check, color="info", outline=True),
                    ], size="auto 8px auto")

                put_html("<hr style='margin: 12px 0; border: none; border-top: 1px solid rgba(125,125,125,0.15);'/>")

        render_cards()

        def update_table():
            with use_scope("updater_info", clear=True):
                local_commit = updater.get_commit(short_sha1=True)
                upstream_commit = updater.get_commit(
                    f"origin/{updater.Branch}", short_sha1=True
                )
                put_table(
                    [
                        [t("Gui.Update.Local"), *(local_commit or ["-", "-", "-", "-"])],
                        [t("Gui.Update.Upstream"), *(upstream_commit or ["-", "-", "-", "-"])],
                    ],
                    header=[
                        "",
                        "SHA1",
                        t("Gui.Update.Author"),
                        t("Gui.Update.Time"),
                        t("Gui.Update.Message"),
                    ],
                )
            with use_scope("updater_detail", clear=True):
                put_text(t("Gui.Update.DetailedHistory"))
                history = updater.get_commit(
                    f"origin/{updater.Branch}", n=20, short_sha1=True
                )
                if history and isinstance(history, list) and len(history) > 0 and history[0]:
                    put_table(
                        [commit for commit in history if commit and len(commit) >= 4],
                        header=[
                            "SHA1",
                            t("Gui.Update.Author"),
                            t("Gui.Update.Time"),
                            t("Gui.Update.Message"),
                        ],
                    )
                else:
                    put_text("暂无提交历史记录或尚未拉取远端分支")

        def u(state):
            if state == -1:
                return
            clear("updater_loading")
            clear("updater_state")
            clear("updater_btn")
            if state == 0:
                put_loading("border", "secondary", "updater_loading").style(
                    "--loading-border-fill--"
                )
                put_text(t("Gui.Update.UpToDate"), scope="updater_state")
                update_table()
            elif state == 1:
                put_loading("grow", "success", "updater_loading").style(
                    "--loading-grow--"
                )
                put_text(t("Gui.Update.HaveUpdate"), scope="updater_state")
                put_button(
                    f"点击更新当前源 ({updater.Branch})",
                    onclick=updater.run_update,
                    color="success",
                    scope="updater_btn",
                )
                update_table()
            elif state == "checking":
                put_loading("border", "primary", "updater_loading").style(
                    "--loading-border--"
                )
                put_text(t("Gui.Update.UpdateChecking"), scope="updater_state")
            elif state == "failed":
                put_loading("grow", "danger", "updater_loading").style(
                    "--loading-grow--"
                )
                put_text(t("Gui.Update.UpdateFailed"), scope="updater_state")
                put_button(
                    t("Gui.Button.RetryUpdate"),
                    onclick=updater.run_update,
                    color="primary",
                    scope="updater_btn",
                )
            elif state == "start":
                put_loading("border", "primary", "updater_loading").style(
                    "--loading-border--"
                )
                put_text(t("Gui.Update.UpdateStart"), scope="updater_state")
                put_button(
                    t("Gui.Button.CancelUpdate"),
                    onclick=updater.cancel,
                    color="danger",
                    scope="updater_btn",
                )
            elif state == "wait":
                put_loading("border", "primary", "updater_loading").style(
                    "--loading-border--"
                )
                put_text(t("Gui.Update.UpdateWait"), scope="updater_state")
                put_button(
                    t("Gui.Button.CancelUpdate"),
                    onclick=updater.cancel,
                    color="danger",
                    scope="updater_btn",
                )
            elif state == "run update":
                put_loading("border", "primary", "updater_loading").style(
                    "--loading-border--"
                )
                put_text(t("Gui.Update.UpdateRun"), scope="updater_state")
                put_button(
                    t("Gui.Button.CancelUpdate"),
                    onclick=updater.cancel,
                    color="danger",
                    scope="updater_btn",
                    disabled=True,
                )
            elif state == "reload":
                put_loading("grow", "success", "updater_loading").style(
                    "--loading-grow--"
                )
                put_text(t("Gui.Update.UpdateSuccess"), scope="updater_state")
                update_table()
            elif state == "finish":
                put_loading("grow", "success", "updater_loading").style(
                    "--loading-grow--"
                )
                put_text(t("Gui.Update.UpdateFinish"), scope="updater_state")
                update_table()
            elif state == "cancel":
                put_loading("border", "danger", "updater_loading").style(
                    "--loading-border--"
                )
                put_text(t("Gui.Update.UpdateCancel"), scope="updater_state")
                put_button(
                    t("Gui.Button.CancelUpdate"),
                    onclick=updater.cancel,
                    color="danger",
                    scope="updater_btn",
                    disabled=True,
                )
            else:
                put_text(
                    "Something went wrong, please contact develops",
                    scope="updater_state",
                )
                put_text(f"state: {state}", scope="updater_state")

        updater_switch = Switch(
            status=u, get_state=lambda: updater.state, name="updater"
        )

        update_table()
        self.task_handler.add(updater_switch.g(), delay=0.5, pending_delete=True)

        updater.check_update()

    @use_scope("content", clear=True)
    def dev_utils(self) -> None:
        self.init_menu(name="Utils")
        self.set_title(t("Gui.MenuDevelop.Utils"))
        put_button(label="Raise exception", onclick=raise_exception)

        def _force_restart():
            if State.restart_event is not None:
                toast("Alas will restart in 3 seconds", duration=0, color="error")
                clearup()
                State.restart_event.set()
            else:
                toast("Reload not enabled", color="error")

        put_button(label="Force restart", onclick=_force_restart)

    @use_scope("content", clear=True)
    def dev_remote(self) -> None:
        self.init_menu(name="Remote")
        self.set_title(t("Gui.MenuDevelop.Remote"))
        put_row(
            content=[put_scope("remote_loading"), None, put_scope("remote_state")],
            size="auto .25rem 1fr",
        )
        put_scope("remote_info")

        def u(state):
            if state == -1:
                return
            clear("remote_loading")
            clear("remote_state")
            clear("remote_info")
            if state in (1, 2):
                put_loading("grow", "success", "remote_loading").style(
                    "--loading-grow--"
                )
                put_text(t("Gui.Remote.Running"), scope="remote_state")
                put_text(t("Gui.Remote.EntryPoint"), scope="remote_info")
                entrypoint = RemoteAccess.get_entry_point()
                if entrypoint:
                    if State.electron:  # Prevent click into url in electron client
                        put_text(entrypoint, scope="remote_info").style(
                            "text-decoration-line: underline"
                        )
                    else:
                        put_link(name=entrypoint, url=entrypoint, scope="remote_info")
                else:
                    put_text("Loading...", scope="remote_info")
            elif state in (0, 3):
                put_loading("border", "secondary", "remote_loading").style(
                    "--loading-border-fill--"
                )
                if (
                        State.deploy_config.EnableRemoteAccess
                        and State.deploy_config.Password
                ):
                    put_text(t("Gui.Remote.NotRunning"), scope="remote_state")
                else:
                    put_text(t("Gui.Remote.NotEnable"), scope="remote_state")
                put_text(t("Gui.Remote.ConfigureHint"), scope="remote_info")
                url = "http://app.azurlane.cloud" + (
                    "" if State.deploy_config.Language.startswith("zh") else "/en.html"
                )
                put_html(
                    f'<a href="{url}" target="_blank">{url}</a>', scope="remote_info"
                )
                if state == 3:
                    put_warning(
                        t("Gui.Remote.SSHNotInstall"),
                        closable=False,
                        scope="remote_info",
                    )

        remote_switch = Switch(
            status=u, get_state=RemoteAccess.get_state, name="remote"
        )

        self.task_handler.add(remote_switch.g(), delay=1, pending_delete=True)

    def ui_develop(self) -> None:
        if not self.is_mobile:
            self.show()
            return
        self.init_aside(name="Home")
        self.set_title(t("Gui.Aside.Home"))
        self.dev_set_menu()
        self.alas_name = ""
        if hasattr(self, "alas"):
            del self.alas
        self.state_switch.switch()

    def ui_alas(self, config_name: str) -> None:
        if config_name == self.alas_name:
            self.expand_menu()
            return
        self.init_aside(name=config_name)
        clear("content")
        self.alas_name = config_name
        self.alas_mod = get_config_mod(config_name)
        self.alas = ProcessManager.get_manager(config_name)
        self.alas_config = load_config(config_name)
        self.state_switch.switch()
        self.initial()
        self.alas_set_menu()

    def ui_add_alas(self) -> None:
        with popup(t("Gui.AddAlas.PopupTitle")) as s:

            def get_unused_name():
                all_name = alas_instance()
                for i in range(2, 100):
                    if f"alas{i}" not in all_name:
                        return f"alas{i}"
                else:
                    return ""

            def add():
                name = pin["AddAlas_name"]
                origin = pin["AddAlas_copyfrom"]

                if name in alas_instance():
                    err = "Gui.AddAlas.FileExist"
                elif set(name) & set(".\\/:*?\"'<>|"):
                    err = "Gui.AddAlas.InvalidChar"
                elif name.lower().startswith("template"):
                    err = "Gui.AddAlas.InvalidPrefixTemplate"
                else:
                    err = ""
                if err:
                    clear(s)
                    put(name, origin)
                    put_error(t(err), scope=s)
                    return

                r = load_config(origin).read_file(origin)
                State.config_updater.write_file(name, r, get_config_mod(origin))
                self.set_aside()
                self.active_button("aside", self.alas_name)
                close_popup()

            def put(name=None, origin=None):
                put_input(
                    name="AddAlas_name",
                    label=t("Gui.AddAlas.NewName"),
                    value=name or get_unused_name(),
                    scope=s,
                )
                put_select(
                    name="AddAlas_copyfrom",
                    label=t("Gui.AddAlas.CopyFrom"),
                    options=alas_template() + alas_instance(),
                    value=origin or "template-alas",
                    scope=s,
                )
                put_buttons(
                    buttons=[
                        {"label": t("Gui.AddAlas.Confirm"), "value": "confirm"},
                        {"label": t("Gui.AddAlas.Manage"), "value": "manage"},
                    ],
                    onclick=[
                        add,
                        lambda: go_app("manage", new_window=False),
                    ],
                    scope=s,
                )

            put()

    def show(self) -> None:
        self._show()
        self.load_home = True
        # Create state_switch before rendering aside buttons, so that
        # ui_alas() (invoked by clicking aside buttons, possibly before
        # the rest of show() finishes on slow machines) never touches an
        # uninitialized member. Reuse existing instance on repeated
        # show() calls (language/theme change, ui_develop) to keep the
        # original single-instance semantics and avoid resetting its
        # internal state generator.
        if not hasattr(self, "state_switch"):
            self.state_switch = Switch(
                status=self.set_status,
                get_state=lambda: getattr(getattr(self, "alas", -1), "state", 0),
                name="state",
            )
        self.set_aside()
        self.init_aside(name="Home")
        self.dev_set_menu()
        self.init_menu(name="HomePage")
        self.alas_name = ""
        if hasattr(self, "alas"):
            del self.alas
        self.set_status(0)

        def set_language(l):
            lang.set_language(l)
            self.show()

        def set_theme(t):
            self.set_theme(t)
            run_js("location.reload()")

        with use_scope("content"):
            put_text("Select your language / 选择语言").style("text-align: center")
            put_buttons(
                [
                    {"label": "简体中文", "value": "zh-CN"},
                    {"label": "繁體中文", "value": "zh-TW"},
                    {"label": "English", "value": "en-US"},
                    {"label": "日本語", "value": "ja-JP"},
                ],
                onclick=lambda l: set_language(l),
            ).style("text-align: center")
            put_text("Change theme / 更改主题").style("text-align: center")
            put_buttons(
                [
                    {"label": "Light", "value": "default", "color": "light"},
                    {"label": "Dark", "value": "dark", "color": "dark"},
                ],
                onclick=lambda t: set_theme(t),
            ).style("text-align: center")

            # show something
            put_markdown(
                """
            Alas is a free open source software, if you paid for Alas from any channel, please refund.
            Alas 是一款免费开源软件，如果你在任何渠道付费购买了Alas，请退款。
            Project repository 项目地址：`https://github.com/LmeSzinc/AzurLaneAutoScript`
            """
            ).style("text-align: center")

        if lang.TRANSLATE_MODE:
            lang.reload()

            def _disable():
                lang.TRANSLATE_MODE = False
                self.show()

            toast(
                _t("Gui.Toast.DisableTranslateMode"),
                duration=0,
                position="right",
                onclick=_disable,
            )

    def run(self) -> None:
        # setup gui
        set_env(title="Alas", output_animation=False)
        add_css(filepath_css("alas"))
        if self.is_mobile:
            add_css(filepath_css("alas-mobile"))
        else:
            add_css(filepath_css("alas-pc"))

        if self.theme == "dark":
            add_css(filepath_css("dark-alas"))
        else:
            add_css(filepath_css("light-alas"))

        # Auto refresh when lost connection
        # [For develop] Disable by run `reload=0` in console
        run_js(
            """
        reload = 1;
        WebIO._state.CurrentSession.on_session_close(
            ()=>{
                setTimeout(
                    ()=>{
                        if (reload == 1){
                            location.reload();
                        }
                    }, 4000
                )
            }
        );

        (function() {
            function purgeDisclaimers() {
                if ($('button.btn-aside-Home.btn-aside-active').length) {
                    return;
                }
                var content = document.getElementById('pywebio-scope-content');
                if (!content) return;
                $('#pywebio-scope-content .markdown').filter(function() {
                    var t = $(this).text();
                    return t.indexOf('paid for Alas') !== -1 || t.indexOf('如果你在任何渠道付费购买') !== -1 || t.indexOf('请退款') !== -1;
                }).remove();
                var walker = document.createTreeWalker(content, NodeFilter.SHOW_TEXT, null, false);
                var toRemove = [];
                var node;
                while (node = walker.nextNode()) {
                    var val = node.nodeValue;
                    if (val && (val.indexOf('paid for Alas') !== -1 || val.indexOf('如果你在任何渠道付费购买') !== -1 || val.indexOf('请退款') !== -1 || val.indexOf('免费开源软件') !== -1)) {
                        toRemove.push(node);
                    }
                }
                for (var i = 0; i < toRemove.length; i++) {
                    var n = toRemove[i];
                    if (n.parentNode && n.parentNode.nodeName === 'P' && n.parentNode.childNodes.length === 1) {
                        n.parentNode.remove();
                    } else if (n.parentNode) {
                        n.parentNode.removeChild(n);
                    }
                }
            }
            window.purgeAlasDisclaimers = purgeDisclaimers;
            if (!window._alas_disclaimer_observer) {
                window._alas_disclaimer_observer = new MutationObserver(purgeDisclaimers);
                window._alas_disclaimer_observer.observe(document.body, {childList: true, subtree: true});
            }
            purgeDisclaimers();
        })();
        """
        )

        aside = get_localstorage("aside")
        self.show()

        # init config watcher
        self._init_alas_config_watcher()

        # save config
        _thread_save_config = threading.Thread(target=self._alas_thread_update_config)
        register_thread(_thread_save_config)
        _thread_save_config.start()

        visibility_state_switch = Switch(
            status={
                True: [
                    lambda: self.__setattr__("visible", True),
                    lambda: self.alas_update_overview_task()
                    if self.page == "Overview"
                    else 0,
                    lambda: self.task_handler._task.__setattr__("delay", 15),
                ],
                False: [
                    lambda: self.__setattr__("visible", False),
                    lambda: self.task_handler._task.__setattr__("delay", 1),
                ],
            },
            get_state=get_window_visibility_state,
            name="visibility_state",
        )

        def goto_update():
            self.ui_develop()
            self.dev_update()

        update_switch = Switch(
            status={
                1: lambda: toast(
                    t("Gui.Toast.ClickToUpdate"),
                    duration=0,
                    position="right",
                    color="success",
                    onclick=goto_update,
                )
            },
            get_state=lambda: updater.state,
            name="update_state",
        )

        self.task_handler.add(self.state_switch.g(), 2)
        self.task_handler.add(self.set_aside_status, 2)
        self.task_handler.add(visibility_state_switch.g(), 15)
        self.task_handler.add(update_switch.g(), 1)
        self.task_handler.start()

        # Return to previous page
        if aside not in ["Home", None]:
            self.ui_alas(aside)


def app_manage():
    def _import():
        resp = file_upload(
            label=t("Gui.AppManage.Import"),
            placeholder=t("Gui.Text.ChooseFile"),
            help_text=t("Gui.AppManage.OverrideWarning"),
            accept=".json",
            required=False,
            max_size="1M",
        )

        if resp is None:
            return

        file: bytes = resp["content"]
        file_name: str = resp["filename"]

        if IS_ON_PHONE_CLOUD:
            config_name = mod_name = "alas"
        elif len(file_name.split(".")) == 2:
            config_name, _ = file_name.split(".")
            mod_name = "alas"
        else:
            config_name, mod_name, _ = file_name.rsplit(".", maxsplit=2)

        config = json.loads(file.decode(encoding="utf-8"))
        State.config_updater.write_file(config_name, config, mod_name)
        toast(t("Gui.AppManage.ImportSuccess"), color="success")

        _show_table()

    def _export(config_name: str):
        mod_name = get_config_mod(config_name)
        if mod_name == "alas":
            filename = f"{config_name}.json"
        else:
            filename = f"{config_name}.{mod_name}.json"
        with open(filepath_config(config_name, mod_name), "rb") as f:
            download(filename, f.read())

    def _new():
        def get_unused_name():
            all_name = alas_instance()
            for i in range(2, 100):
                if f"alas{i}" not in all_name:
                    return f"alas{i}"
            else:
                return ""

        def validate(s: str):
            if s in alas_instance():
                return t("Gui.AppManage.NameExist")
            if set(s) & set(".\\/:*?\"'<>|"):
                return t("Gui.AppManage.InvalidChar")
            if s.lower().startswith("template"):
                return t("Gui.AppManage.InvalidPrefixTemplate")
            return None

        resp = input_group(
            label=t("Gui.AppManage.TitleNew"),
            inputs=[
                input(
                    label=t("Gui.AppManage.NewName"),
                    name="config_name",
                    value=get_unused_name(),
                    validate=validate,
                ),
                select(
                    label=t("Gui.AppManage.CopyFrom"),
                    name="copy_from",
                    options=alas_template() + alas_instance(),
                    value="template-alas",
                ),
            ],
            cancelable=True,
        )

        if resp is None:
            return

        config_name = resp["config_name"]
        origin = resp["copy_from"]

        r = load_config(origin).read_file(origin)
        State.config_updater.write_file(config_name, r, get_config_mod(origin))
        toast(t("Gui.AppManage.NewSuccess"), color="success")
        _show_table()

    def _show_table():
        clear("config_table")
        put_table(
            tdata=[
                (
                    name,
                    get_config_mod(name),
                    put_buttons(
                        buttons=[
                            {"label": t("Gui.AppManage.Export"), "value": name},
                            # {
                            #     "label": t("Gui.AppManage.Delete"),
                            #     "value": name,
                            #     "disabled": True,
                            #     "color": "danger",
                            # },
                        ],
                        onclick=[
                            partial(_export, name),
                            # partial(_delete, name),
                        ],
                        group=True,
                        small=True,
                    ),
                )
                for name in alas_instance()
            ],
            header=[
                t("Gui.AppManage.Name"),
                t("Gui.AppManage.Mod"),
                t("Gui.AppManage.Actions"),
            ],
            scope="config_table",
        )

    set_env(title="Alas", output_animation=False)
    run_js("$('head').append('<style>.footer{display:none}</style>')")

    put_html(f"<h2>{t('Gui.AppManage.PageTitle')}</h2>")
    put_scope("config_table")
    put_buttons(
        buttons=[
            {
                "label": t("Gui.AppManage.New"),
                "value": "new",
                "disabled": IS_ON_PHONE_CLOUD,
            },
            {"label": t("Gui.AppManage.Import"), "value": "import"},
            {"label": t("Gui.AppManage.Back"), "value": "back"},
        ],
        onclick=[
            (lambda: None) if IS_ON_PHONE_CLOUD else _new,
            _import,
            partial(go_app, "index", new_window=False),
        ],
    )
    _show_table()


def debug():
    """For interactive python.
    $ python3
    >>> from module.webui.app import *
    >>> debug()
    >>>
    """
    startup()
    AlasGUI().run()


def startup():
    State.init()
    lang.reload()
    updater.event = State.manager.Event()
    if updater.delay > 0:
        task_handler.add(updater.check_update, updater.delay)
    task_handler.add(updater.schedule_update(), 86400)
    task_handler.start()
    if State.deploy_config.DiscordRichPresence:
        init_discord_rpc()
    if State.deploy_config.StartOcrServer:
        start_ocr_server_process(State.deploy_config.OcrServerPort)
    if (
            State.deploy_config.EnableRemoteAccess
            and State.deploy_config.Password is not None
    ):
        task_handler.add(RemoteAccess.keep_ssh_alive(), 60)


def clearup():
    """
    Notice: Ensure run it before uvicorn reload app,
    all process will NOT EXIT after close electron app.
    """
    logger.info("Start clearup")
    RemoteAccess.kill_ssh_process()
    close_discord_rpc()
    stop_ocr_server_process()
    for alas in ProcessManager._processes.values():
        alas.stop()
    State.clearup()
    task_handler.stop()
    logger.info("Alas closed.")


def app():
    parser = argparse.ArgumentParser(description="Alas web service")
    parser.add_argument(
        "-k", "--key", type=str, help="Password of alas. No password by default"
    )
    parser.add_argument(
        "--cdn",
        action="store_true",
        help="Use jsdelivr cdn for pywebio static files (css, js). Self host cdn by default.",
    )
    parser.add_argument(
        "--run",
        nargs="+",
        type=str,
        help="Run alas by config names on startup",
    )
    args, _ = parser.parse_known_args()

    # Apply config
    AlasGUI.set_theme(theme=State.deploy_config.Theme)
    lang.LANG = State.deploy_config.Language
    key = args.key or State.deploy_config.Password
    cdn = args.cdn if args.cdn else State.deploy_config.CDN
    runs = None
    if args.run:
        runs = args.run
    elif State.deploy_config.Run:
        # TODO: refactor poor_yaml_read() to support list
        tmp = State.deploy_config.Run.split(",")
        runs = [l.strip(" ['\"]") for l in tmp if len(l)]
    instances: List[str] = runs

    logger.hr("Webui configs")
    logger.attr("Theme", State.deploy_config.Theme)
    logger.attr("Language", lang.LANG)
    logger.attr("Password", True if key else False)
    logger.attr("CDN", cdn)
    logger.attr("IS_ON_PHONE_CLOUD", IS_ON_PHONE_CLOUD)

    from deploy.atomic import atomic_failure_cleanup
    atomic_failure_cleanup('./config')

    def index():
        if key is not None and not login(key):
            logger.warning(f"{info.user_ip} login failed.")
            time.sleep(1.5)
            run_js("location.reload();")
            return
        gui = AlasGUI()
        local.gui = gui
        gui.run()

    def manage():
        if key is not None and not login(key):
            logger.warning(f"{info.user_ip} login failed.")
            time.sleep(1.5)
            run_js("location.reload();")
            return
        app_manage()

    app = asgi_app(
        applications=[index, manage],
        cdn=cdn,
        static_dir=None,
        debug=True,
        on_startup=[
            startup,
            lambda: ProcessManager.restart_processes(
                instances=instances, ev=updater.event
            ),
        ],
        on_shutdown=[clearup],
    )

    return app
