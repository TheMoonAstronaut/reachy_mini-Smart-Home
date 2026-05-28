"""Light action system for Reachy Mini.

Light ON -> Random dance -> Return to neutral
Light OFF -> Sleep/contraction pose
"""

import asyncio
import logging
import random
from typing import Optional, TYPE_CHECKING

import numpy as np

from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose
from reachy_mini.reachy_mini import SLEEP_HEAD_POSE as SDK_SLEEP_HEAD_POSE
from reachy_mini.reachy_mini import SLEEP_ANTENNAS_JOINT_POSITIONS as SDK_SLEEP_ANTENNAS
from .move_queue import (
    MovementManager,
    GotoQueueMove,
    DanceQueueMove,
)
from .poses import NEUTRAL_POSE

import robot as robot_module
get_shared_robot = robot_module.get_shared_robot

logger = logging.getLogger(__name__)


def _load_dance_library():
    """Lazy load dance library."""
    try:
        from reachy_mini_dances_library.collection.dance import AVAILABLE_MOVES
        from reachy_mini_dances_library.dance_move import DanceMove
        logger.info(f"[DANCE] Loaded {len(AVAILABLE_MOVES)} dance moves")
        return True, AVAILABLE_MOVES, DanceMove
    except ImportError as e:
        logger.warning(f"[DANCE] Library import failed: {e}")
        return False, {}, None


DANCE_STATUS = None  # Cached status: None=not tried, True=success, False=failed
DANCE_AVAILABLE = False
AVAILABLE_MOVES = {}
DanceMove = None


def _ensure_dance_library():
    """Ensure dance library is loaded. Always retries on failure to handle late imports."""
    global DANCE_STATUS, DANCE_AVAILABLE, AVAILABLE_MOVES
    if DANCE_STATUS is not True:  # Either None or False, always retry if not successful
        status, moves, _ = _load_dance_library()
        if status:
            DANCE_STATUS = True
            DANCE_AVAILABLE = True
            AVAILABLE_MOVES = moves
        else:
            DANCE_STATUS = False
    return DANCE_AVAILABLE, AVAILABLE_MOVES


class LightActions:
    """Handler for light-related actions (ON/OFF)."""

    def __init__(
        self,
        movement_manager: MovementManager,
        robot: Optional[ReachyMini] = None,
    ):
        """Initialize light actions."""
        self.movement_manager = movement_manager
        self._robot = robot
        self._action_complete_event: Optional[asyncio.Event] = None
        _ensure_dance_library()

    @property
    def robot(self) -> ReachyMini:
        """Get robot instance."""
        if self._robot is None:
            self._robot = get_shared_robot()
        return self._robot

    async def do_light_action(self, command: str) -> None:
        """Execute light action based on command.

        Args:
            command: Either "Light_ON" or "Light_OFF".
        """
        if command not in ("Light_ON", "Light_OFF"):
            return

        is_on = command == "Light_ON"

        if is_on:
            await self._do_light_on()
        else:
            await self._do_light_off()

    async def _do_light_on(self) -> None:
        """Light ON: Smooth transition from any state to neutral, then dance."""
        logger.info("[ACTION] Light ON: Starting dance sequence")

        self.movement_manager.set_sleep_mode(False)
        self.movement_manager.clear_move_queue()

        at_sleep = self.movement_manager.is_at_sleep_pose()

        if at_sleep:
            logger.info("[ACTION] Currently at sleep pose, returning to neutral first")
            await self._go_to_neutral()

        available, moves = _ensure_dance_library()
        if not available or not moves:
            logger.warning("[ACTION] Dance library not available, skipping dance")
            return

        dance_name = random.choice(list(moves.keys()))
        logger.info(f"[ACTION] Selected dance: {dance_name}")

        dance_queue_move = DanceQueueMove(dance_name)
        self.movement_manager.queue_move(dance_queue_move)
        self.movement_manager.set_moving_state(dance_queue_move.duration)

        await asyncio.sleep(dance_queue_move.duration + 0.5)

        await self._go_to_neutral()
        logger.info("[ACTION] Light ON sequence complete")

    async def _do_light_off(self) -> None:
        """Light OFF: Go to sleep/contracted pose."""
        logger.info("[ACTION] Light OFF: Going to sleep pose")

        self.movement_manager.clear_move_queue()
        self.movement_manager.set_sleep_mode(True)
        await self._go_to_sleep_pose()
        logger.info("[ACTION] Light OFF sequence complete")

    async def _go_to_neutral(self) -> None:
        """Move to neutral pose."""
        neutral_head = NEUTRAL_POSE.head_pose
        neutral_antennas = NEUTRAL_POSE.antennas
        neutral_body_yaw = NEUTRAL_POSE.body_yaw

        current_head = self.robot.get_current_head_pose()
        _, current_antennas = self.robot.get_current_joint_positions()

        goto_move = GotoQueueMove(
            target_head_pose=neutral_head.astype(np.float32),
            start_head_pose=current_head.astype(np.float32),
            target_antennas=neutral_antennas,
            start_antennas=(float(current_antennas[0]), float(current_antennas[1])),
            target_body_yaw=neutral_body_yaw,
            start_body_yaw=float(current_antennas[0]),
            duration=1.5,
        )

        self.movement_manager.queue_move(goto_move)
        self.movement_manager.set_moving_state(1.5)

        await asyncio.sleep(2.0)

    async def _go_to_sleep_pose(self) -> None:
        """Move to sleep/contracted pose using SDK's SLEEP_HEAD_POSE."""
        sleep_head = SDK_SLEEP_HEAD_POSE.astype(np.float32)
        sleep_antennas = SDK_SLEEP_ANTENNAS

        current_head = self.robot.get_current_head_pose()
        _, current_antennas = self.robot.get_current_joint_positions()

        goto_move = GotoQueueMove(
            target_head_pose=sleep_head,
            start_head_pose=current_head.astype(np.float32),
            target_antennas=sleep_antennas,
            start_antennas=(float(current_antennas[0]), float(current_antennas[1])),
            target_body_yaw=0.0,
            start_body_yaw=float(current_antennas[0]),
            duration=2.0,
        )

        self.movement_manager.queue_move(goto_move)
        self.movement_manager.set_moving_state(2.0)

        await asyncio.sleep(2.5)


def create_light_actions(movement_manager: MovementManager) -> LightActions:
    """Factory function to create LightActions."""
    return LightActions(movement_manager=movement_manager)
