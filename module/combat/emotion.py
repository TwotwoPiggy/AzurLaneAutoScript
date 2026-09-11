from datetime import datetime
from time import sleep

import numpy as np

from module.base.decorator import cached_property
from module.base.utils import random_normal_distribution_int
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from module.config.config import AzurLaneConfig
from module.exception import ScriptEnd, ScriptError, RequestHumanTakeover
from module.logger import logger

DIC_LIMIT = {
    'keep_exp_bonus': 120,
    'prevent_green_face': 40,
    'prevent_yellow_face': 30,
    'prevent_red_face': 2,
}
DIC_RECOVER = {
    'not_in_dormitory': 20,
    'dormitory_floor_1': 40,
    'dormitory_floor_2': 50,
}
DIC_RECOVER_MAX = {
    'not_in_dormitory': 119,
    'dormitory_floor_1': 150,
    'dormitory_floor_2': 150,
}
OATH_RECOVER = 10


class FleetEmotion:
    def __init__(self, config, fleet):
        """
        Args:
            config (AzurLaneConfig):
            fleet (int): Fleet index
        """
        self.config = config
        self.fleet = fleet
        self.current = 0

    @property
    def value(self):
        """
        Returns:
            int: 0 to 150
        """
        return getattr(self.config, f'Emotion_Fleet{self.fleet}Value')

    @property
    def value_name(self):
        """
        Returns:
            str:
        """
        return f'Emotion_Fleet{self.fleet}Value'

    @property
    def record(self):
        """
        Returns:
            datetime.datetime:
        """
        return getattr(self.config, f'Emotion_Fleet{self.fleet}Record')

    @property
    def recover(self):
        """
        Returns:
            str: not_in_dormitory, dormitory_floor_1, dormitory_floor_2
        """
        return getattr(self.config, f'Emotion_Fleet{self.fleet}Recover')

    @property
    def control(self):
        """
        Returns:
            str: keep_exp_bonus, prevent_green_face, prevent_yellow_face, prevent_red_face
        """
        return getattr(self.config, f'Emotion_Fleet{self.fleet}Control')

    @property
    def oath(self):
        """
        Returns:
            bool: If all ships oath.
        """
        return getattr(self.config, f'Emotion_Fleet{self.fleet}Oath')

    @property
    def speed(self):
        """
        Returns:
            int: Recover speed per 6 min.
        """
        speed = DIC_RECOVER[self.recover]
        if self.oath:
            speed += OATH_RECOVER
        return speed // 10

    @property
    def limit(self):
        """
        Returns:
            int: Minimum emotion value to control
        """
        return DIC_LIMIT[self.control]

    @property
    def max(self):
        """
        Returns:
            int: Maximum emotion value
        """
        return DIC_RECOVER_MAX[self.recover]

    def update(self):
        recover_count = int(int(datetime.now().timestamp()) // 360 - int(self.record.timestamp()) // 360)
        recover_count = max(recover_count, 0)
        self.current = min(max(self.value, 0) + self.speed * recover_count, self.max)

    def get_recovered(self, expected_reduce=0):
        """
        Args:
            expected_reduce (int):

        Returns:
            datetime.datetime: When will emotion >= control limit.
                If already recovered, return time in the past.
        """
        if self.control == 'keep_exp_bonus' and self.recover == 'not_in_dormitory':
            logger.critical(f'Fleet {self.fleet} Emotion Control=\"Keep Happy Bonus\" and '
                            f'Fleet {self.fleet} Recover Location=\"Docks\" can not be used together, '
                            'please check your emotion settings')
            raise RequestHumanTakeover
        # In 14-4 with 2X book, expected emotion reduce is 32, can't keep happy bonus (>120),
        # otherwise will infinite task delay
        if self.control == 'keep_exp_bonus' and expected_reduce >= 29:
            expected_reduce = 29
            logger.info(f'Fleet {self.fleet} expected_reduce is limited to 29 '
                        f'when Emotion Control=\"Keep Happy Bonus\"')

        recover_count = (self.limit + expected_reduce - self.current) // self.speed
        recovered = (int(datetime.now().timestamp()) // 360 + recover_count + 1) * 360
        return datetime.fromtimestamp(recovered)


class Emotion:
    total_reduced = 0
    map_is_2x_book = False

    def __init__(self, config):
        """
        Args:
            config (AzurLaneConfig):
        """
        self.config = config
        self.fleet_1 = FleetEmotion(self.config, fleet=1)
        self.fleet_2 = FleetEmotion(self.config, fleet=2)
        self.fleets = [self.fleet_1, self.fleet_2]
        self.primary_fleet_order = self.config.Fleet_FleetOrder

    @property
    def is_calculate(self):
        return 'calculate' in self.config.Emotion_Mode

    @property
    def is_ignore(self):
        return 'ignore' in self.config.Emotion_Mode

    def update(self):
        """
        Update emotion value. This should be called before doing anything.
        """
        for fleet in self.fleets:
            fleet.update()

    def record(self):
        """
        Save current emotion value to config.
        """
        value = {}
        for fleet in self.fleets:
            value[fleet.value_name] = fleet.current

        self.config.set_record(**value)

    def show(self):
        for fleet in self.fleets:
            logger.attr(f'Emotion fleet_{fleet.fleet}', fleet.value)

    @property
    def reduce_per_battle(self):
        if self.map_is_2x_book:
            return 4
        else:
            return 2

    @property
    def reduce_per_battle_before_entering(self):
        if self.map_is_2x_book:
            return 4
        elif self.config.Campaign_Use2xBook:
            return 4
        else:
            return 2

    def get_expected_reduce(self, order, battle):
        """
        Calculate expected emotion reduction for each fleet under the given fleet order.

        Args:
            order (str): Fleet order name
            battle (int): Total battles

        Returns:
            tuple[int, int] | None: Reduction for fleet 1 and fleet 2, or None if invalid.
        """
        if order == 'fleet1_mob_fleet2_boss':
            distribution = (battle - 1, 1)
        elif order == 'fleet1_boss_fleet2_mob':
            distribution = (1, battle - 1)
        elif order == 'fleet1_all_fleet2_standby':
            distribution = (battle, 0)
        elif order == 'fleet1_standby_fleet2_all':
            distribution = (0, battle)
        else:
            return None

        return tuple(np.array(distribution) * self.reduce_per_battle_before_entering)

    def is_order_available(self, order, battle):
        """
        Check if the given fleet order has enough emotion to sortie without delay.

        Args:
            order (str): Fleet order name
            battle (int): Total battles

        Returns:
            bool: True if all fleets can sortie without delay.
        """
        reduce_amounts = self.get_expected_reduce(order, battle)
        if reduce_amounts is None:
            return False

        recovered = max([f.get_recovered(b) for f, b in zip(self.fleets, reduce_amounts)])
        return recovered <= datetime.now()

    def should_switch_fleet_order(self, battle):
        """
        Check and execute switching between primary and backup fleet orders.

        Priority Rules:
        1. If backup is disabled or same as primary, do nothing.
        2. If currently on backup order:
           - If primary order has recovered, switch back to primary order.
        3. If currently on primary order:
           - If primary order is not available, but backup order is available,
             switch to backup order.

        Args:
            battle (int): Battles in this campaign

        Returns:
            bool: If fleet order was changed.
        """
        if not self.is_calculate:
            return False
        if not self.config.FLEET_2:
            return False

        backup_order = getattr(self.config, 'Fleet_FleetOrderBackup', 'disabled')
        if not backup_order or backup_order == 'disabled':
            return False

        primary_order = getattr(self, 'primary_fleet_order', None)
        if not primary_order:
            self.primary_fleet_order = self.config.Fleet_FleetOrder
            primary_order = self.primary_fleet_order

        if backup_order == primary_order:
            return False

        current_order = self.config.Fleet_FleetOrder
        self.update()

        # Rule 1: Currently running backup order -> switch back to primary if recovered
        if current_order == backup_order:
            if self.is_order_available(primary_order, battle):
                logger.hr('Fleet Order Switch', level=1)
                logger.info(
                    f'Primary fleet order `{primary_order}` has recovered. Switching back from backup `{backup_order}`.'
                )
                self.config.Fleet_FleetOrder = primary_order
                self.config.override(Fleet_FleetOrder=primary_order)
                logger.attr('Fleet_FleetOrder', primary_order)
                return True
            return False

        # Rule 2: Currently running primary order -> switch to backup if primary exhausted
        if current_order == primary_order:
            if not self.is_order_available(primary_order, battle):
                if self.is_order_available(backup_order, battle):
                    logger.hr('Fleet Order Switch', level=1)
                    logger.info(
                        f'Primary fleet order `{primary_order}` cannot sortie due to emotion limit.'
                    )
                    logger.info(
                        f'Switching to backup fleet order `{backup_order}` for seamless sortie.'
                    )
                    self.config.Fleet_FleetOrder = backup_order
                    self.config.override(Fleet_FleetOrder=backup_order)
                    logger.attr('Fleet_FleetOrder', backup_order)
                    return True

        return False

    def check_reduce(self, battle):
        """
        Check emotion before entering a campaign.

        Args:
            battle (int): Battles in this campaign

        Raise:
            ScriptEnd: Delay current task to prevent emotion control in the future.
        """
        if not self.is_calculate:
            return

        total_battle = battle

        # Pre-check if we should switch back to primary order or switch to backup
        if self.should_switch_fleet_order(total_battle):
            return self.check_reduce(total_battle)

        method = self.config.Fleet_FleetOrder
        reduce_amounts = self.get_expected_reduce(method, battle)
        if reduce_amounts is None:
            raise ScriptError(f'Unknown fleet order: {method}')

        logger.info(f'Expect emotion reduce: {reduce_amounts}')

        self.update()
        self.record()
        self.show()
        recovered = max([f.get_recovered(b) for f, b in zip(self.fleets, reduce_amounts)])
        if recovered > datetime.now():
            if self.should_switch_fleet_order(total_battle):
                return self.check_reduce(total_battle)

            logger.info('Delay current task to prevent emotion control in the future')
            self.config.task_delay(target=recovered)
            raise ScriptEnd('Emotion control')

    def wait(self, fleet_index):
        """
        Wait emotion of specific fleet.
        Should be called before entering any battles.

        Args:
            fleet_index (int): 1 or 2.
        """
        self.update()
        self.record()
        self.show()
        fleet = self.fleets[fleet_index - 1]
        recovered = fleet.get_recovered(expected_reduce=self.reduce_per_battle)
        if recovered > datetime.now():
            logger.hr('Emotion wait')
            logger.info(f'Emotion of fleet {fleet_index} will recover to {fleet.limit} at {recovered}')

            while 1:
                if datetime.now() > recovered:
                    break

                logger.attr('Wait until', recovered)
                sleep(60)

    def reduce(self, fleet_index):
        """
        Reduce emotion of specific fleet.
        Should be called after battle executing.
        On server side, emotion is reduced once battle loading finished.

        Args:
            fleet_index (int): 1 or 2.
        """
        logger.hr('Emotion reduce')
        self.update()

        fleet = self.fleets[fleet_index - 1]
        fleet.current -= self.reduce_per_battle
        self.total_reduced += self.reduce_per_battle
        self.record()
        self.show()

    @cached_property
    def bug_threshold(self):
        """
        Returns:
            int:
        """
        return random_normal_distribution_int(55, 105, n=2)

    def bug_threshold_reset(self):
        """ Call this method after emotion bug triggered. """
        del self.__dict__['bug_threshold']

    def triggered_bug(self):
        """
        Azur Lane client does not calculate emotion correctly, which is a bug.
        After a long run, we have to restart game client and let the client update it.
        """
        logger.attr('Emotion_bug', f'{self.total_reduced}/{self.bug_threshold}')
        if self.total_reduced >= self.bug_threshold:
            logger.info('Azur Lane client does not calculate emotion correctly, which is a bug. '
                        'After a long run, we have to restart game client and let the client update it.')
            self.total_reduced = 0
            self.bug_threshold_reset()
            return True
        else:
            return False
