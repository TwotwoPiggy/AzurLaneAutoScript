from datetime import datetime, timedelta
import sys
from unittest.mock import MagicMock

if 'cv2' not in sys.modules:
    try:
        import cv2
    except ImportError:
        sys.modules['cv2'] = MagicMock()

import pytest

from module.combat.emotion import Emotion
from module.exception import ScriptEnd


class FakeConfig:
    """Mock config for testing Emotion and fleet order primary/backup switching."""

    def __init__(
        self,
        fleet_order='fleet1_mob_fleet2_boss',
        fleet_order_backup='disabled',
        fleet1_value=140,
        fleet2_value=140,
        fleet1_control='prevent_green_face',
        fleet2_control='prevent_green_face',
        fleet1_recover='dormitory_floor_2',
        fleet2_recover='dormitory_floor_2',
        fleet2_enabled=2,
    ):
        self.Emotion_Mode = 'calculate'
        self.Campaign_Use2xBook = False
        self.Fleet_FleetOrder = fleet_order
        self.Fleet_FleetOrderBackup = fleet_order_backup
        self.FLEET_2 = fleet2_enabled

        self.Emotion_Fleet1Value = fleet1_value
        self.Emotion_Fleet1Record = datetime.now() - timedelta(minutes=1)
        self.Emotion_Fleet1Control = fleet1_control
        self.Emotion_Fleet1Recover = fleet1_recover
        self.Emotion_Fleet1Oath = False

        self.Emotion_Fleet2Value = fleet2_value
        self.Emotion_Fleet2Record = datetime.now() - timedelta(minutes=1)
        self.Emotion_Fleet2Control = fleet2_control
        self.Emotion_Fleet2Recover = fleet2_recover
        self.Emotion_Fleet2Oath = False

        self.overridden = {}
        self.delayed_target = None

    def override(self, **kwargs):
        self.overridden.update(kwargs)
        for k, v in kwargs.items():
            setattr(self, k, v)

    def set_record(self, **kwargs):
        pass

    def task_delay(self, target=None):
        self.delayed_target = target


class TestEmotionFleetOrderSwitch:
    def test_switch_to_backup_when_primary_fleet2_mob_low_emotion(self):
        """
        Scenario:
        Primary order: fleet1_boss_fleet2_mob (Fleet 1 Boss, Fleet 2 Mob).
        Backup order: fleet1_mob_fleet2_boss.
        Fleet 2 is tired (emotion 45, control=40, battles=5 mob -> reduces 10 -> would become 35 < 40).
        Fleet 1 is full (emotion 140 -> can easily handle 5 mob battles).
        Should switch to backup (fleet1_mob_fleet2_boss) and proceed without delay.
        """
        config = FakeConfig(
            fleet_order='fleet1_boss_fleet2_mob',
            fleet_order_backup='fleet1_mob_fleet2_boss',
            fleet1_value=140,
            fleet2_value=45,
            fleet1_control='prevent_green_face',  # limit 40
            fleet2_control='prevent_green_face',  # limit 40
        )
        emotion = Emotion(config)

        # 6 total battles: 5 mob + 1 boss
        # In primary order: Fleet 2 would reduce 5 * 2 = 10 -> current 45 - 10 = 35 < 40 (fails!)
        # Backup order: Fleet 1 reduces 10 (140 -> 130 >= 40), Fleet 2 reduces 2 (45 -> 43 >= 40) (passes!)
        switched = emotion.should_switch_fleet_order(battle=6)
        assert switched is True
        assert config.Fleet_FleetOrder == 'fleet1_mob_fleet2_boss'

        # check_reduce should not raise ScriptEnd now
        emotion.check_reduce(battle=6)
        assert config.Fleet_FleetOrder == 'fleet1_mob_fleet2_boss'

    def test_switch_to_backup_when_primary_fleet1_mob_low_emotion(self):
        """
        Scenario:
        Primary order: fleet1_mob_fleet2_boss (Fleet 1 Mob, Fleet 2 Boss).
        Backup order: fleet1_boss_fleet2_mob.
        Fleet 1 is tired (emotion 45, control=40).
        Fleet 2 is healthy (emotion 140).
        Should switch to backup order fleet1_boss_fleet2_mob.
        """
        config = FakeConfig(
            fleet_order='fleet1_mob_fleet2_boss',
            fleet_order_backup='fleet1_boss_fleet2_mob',
            fleet1_value=45,
            fleet2_value=140,
            fleet1_control='prevent_green_face',  # limit 40
            fleet2_control='prevent_green_face',  # limit 40
        )
        emotion = Emotion(config)

        switched = emotion.should_switch_fleet_order(battle=6)
        assert switched is True
        assert config.Fleet_FleetOrder == 'fleet1_boss_fleet2_mob'

        # check_reduce should succeed without delay
        emotion.check_reduce(battle=6)
        assert config.Fleet_FleetOrder == 'fleet1_boss_fleet2_mob'

    def test_switch_back_to_primary_when_primary_recovered(self):
        """
        Scenario:
        Primary was fleet1_mob_fleet2_boss, backup is fleet1_boss_fleet2_mob.
        Currently running on backup order (fleet1_boss_fleet2_mob).
        Now Fleet 1 has recovered in dorm (emotion 140).
        Should switch back to primary order.
        """
        config = FakeConfig(
            fleet_order='fleet1_mob_fleet2_boss',
            fleet_order_backup='fleet1_boss_fleet2_mob',
            fleet1_value=140,
            fleet2_value=140,
            fleet1_control='prevent_green_face',
            fleet2_control='prevent_green_face',
        )
        emotion = Emotion(config)
        # Simulate that we previously switched to backup
        config.Fleet_FleetOrder = 'fleet1_boss_fleet2_mob'

        switched = emotion.should_switch_fleet_order(battle=6)
        assert switched is True
        assert config.Fleet_FleetOrder == 'fleet1_mob_fleet2_boss'

        # Subsequent check_reduce stays on primary
        emotion.check_reduce(battle=6)
        assert config.Fleet_FleetOrder == 'fleet1_mob_fleet2_boss'

    def test_single_fleet_all_standby_backup_switch(self):
        """
        Scenario:
        Primary order: fleet1_all_fleet2_standby.
        Backup order: fleet1_standby_fleet2_all.
        Fleet 1 is tired (emotion 45, 6 battles * 2 = 12 reduce -> 33 < 40).
        Fleet 2 is healthy (emotion 140).
        Should switch to backup order fleet1_standby_fleet2_all.
        """
        config = FakeConfig(
            fleet_order='fleet1_all_fleet2_standby',
            fleet_order_backup='fleet1_standby_fleet2_all',
            fleet1_value=45,
            fleet2_value=140,
            fleet1_control='prevent_green_face',
            fleet2_control='prevent_green_face',
        )
        emotion = Emotion(config)

        switched = emotion.should_switch_fleet_order(battle=6)
        assert switched is True
        assert config.Fleet_FleetOrder == 'fleet1_standby_fleet2_all'

        emotion.check_reduce(battle=6)
        assert config.Fleet_FleetOrder == 'fleet1_standby_fleet2_all'

    def test_no_switch_when_disabled(self):
        """When backup is 'disabled', no switch should occur and ScriptEnd should be raised."""
        config = FakeConfig(
            fleet_order='fleet1_boss_fleet2_mob',
            fleet_order_backup='disabled',
            fleet1_value=140,
            fleet2_value=45,
            fleet1_control='prevent_green_face',
            fleet2_control='prevent_green_face',
        )
        emotion = Emotion(config)

        assert emotion.should_switch_fleet_order(battle=6) is False
        assert config.Fleet_FleetOrder == 'fleet1_boss_fleet2_mob'

        with pytest.raises(ScriptEnd):
            emotion.check_reduce(battle=6)

    def test_no_switch_when_backup_same_as_primary(self):
        """When backup order is identical to primary order, no switch occurs."""
        config = FakeConfig(
            fleet_order='fleet1_mob_fleet2_boss',
            fleet_order_backup='fleet1_mob_fleet2_boss',
            fleet1_value=45,
            fleet2_value=140,
            fleet1_control='prevent_green_face',
            fleet2_control='prevent_green_face',
        )
        emotion = Emotion(config)

        assert emotion.should_switch_fleet_order(battle=6) is False
        with pytest.raises(ScriptEnd):
            emotion.check_reduce(battle=6)

    def test_both_fleets_exhausted(self):
        """When both orders cannot fulfill emotion requirements, raise ScriptEnd."""
        config = FakeConfig(
            fleet_order='fleet1_mob_fleet2_boss',
            fleet_order_backup='fleet1_boss_fleet2_mob',
            fleet1_value=30,
            fleet2_value=30,
            fleet1_control='prevent_green_face',
            fleet2_control='prevent_green_face',
        )
        emotion = Emotion(config)

        assert emotion.should_switch_fleet_order(battle=6) is False
        with pytest.raises(ScriptEnd):
            emotion.check_reduce(battle=6)

    def test_healthy_fleets_do_not_switch(self):
        """When current primary order has plenty of emotion, do not switch to backup."""
        config = FakeConfig(
            fleet_order='fleet1_mob_fleet2_boss',
            fleet_order_backup='fleet1_boss_fleet2_mob',
            fleet1_value=140,
            fleet2_value=140,
            fleet1_control='prevent_green_face',
            fleet2_control='prevent_green_face',
        )
        emotion = Emotion(config)

        assert emotion.should_switch_fleet_order(battle=6) is False
        emotion.check_reduce(battle=6)
        assert config.Fleet_FleetOrder == 'fleet1_mob_fleet2_boss'

    def test_stay_on_backup_when_primary_not_yet_recovered(self):
        """When running backup order and primary has NOT recovered, stay on backup."""
        config = FakeConfig(
            fleet_order='fleet1_mob_fleet2_boss',
            fleet_order_backup='fleet1_boss_fleet2_mob',
            fleet1_value=45,
            fleet2_value=140,
            fleet1_control='prevent_green_face',
            fleet2_control='prevent_green_face',
        )
        emotion = Emotion(config)
        # Running on backup: Fleet 1 is Boss (45 - 2 = 43 >= 40), Fleet 2 is Mob (140 - 10 = 130 >= 40)
        config.Fleet_FleetOrder = 'fleet1_boss_fleet2_mob'

        # Primary order requires Fleet 1 as Mob (45 - 10 = 35 < 40), which is not yet recovered.
        # Should stay on backup!
        switched = emotion.should_switch_fleet_order(battle=6)
        assert switched is False
        assert config.Fleet_FleetOrder == 'fleet1_boss_fleet2_mob'

        emotion.check_reduce(battle=6)
        assert config.Fleet_FleetOrder == 'fleet1_boss_fleet2_mob'
