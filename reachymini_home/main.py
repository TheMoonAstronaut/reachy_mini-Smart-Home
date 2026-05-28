"""Main entry point for Reachy Mini Motor - Voice Controlled Action System.

Coordinates:
- ASR (Doubao streaming speech recognition)
- Brain (Doubao LLM intent parsing)
- TTS (Edge TTS speech synthesis)
- Actions (Dance on light ON, Sleep on light OFF)
- Network (TCP to XIAO servo controller)
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import asyncio
import logging
import time
from typing import Optional

import utils

import config
import asr
import brain
import tts
import network
import audio
import robot
from actions.move_queue import MovementManager
from actions.light_actions import create_light_actions

logger = logging.getLogger(__name__)


class ReachyMotorSystem:
    """Main system coordinating all components."""

    def __init__(self):
        """Initialize all components."""
        self.audio: Optional[audio.ReachyAudioInput] = None
        self.brain: Optional[brain.DoubaoBrain] = None
        self.tts: Optional[tts.EdgeTTS] = None
        self.movement_manager: Optional[MovementManager] = None
        self.light_actions = None

    async def initialize(self) -> None:
        """Initialize all system components."""
        logger.info("=" * 60)
        logger.info("  Reachy Mini Motor System")
        logger.info("  Voice Controlled Action System")
        logger.info("=" * 60)

        logger.info("[INIT] Initializing robot...")
        r = robot.get_shared_robot()
        logger.info("[INIT] Robot ready")

        logger.info("[INIT] Starting movement manager...")
        self.movement_manager = MovementManager(current_robot=r)
        self.movement_manager.start()
        logger.info("[INIT] Movement manager started")

        self.light_actions = create_light_actions(self.movement_manager)
        logger.info("[INIT] Light actions ready")

        self.audio = audio.ReachyAudioInput()
        self.audio.start()
        logger.info("[INIT] Audio input ready")

        self.brain = brain.DoubaoBrain(provider=config.BRAIN_CONFIG["provider"])
        logger.info("[INIT] Brain ready")

        self.tts = tts.EdgeTTS(voice=config.TTS_CONFIG["voice"])
        logger.info("[INIT] TTS ready")

        logger.info("[INIT] All components initialized")

    async def cleanup(self) -> None:
        """Cleanup resources."""
        logger.info("[CLEANUP] Shutting down...")

        if self.movement_manager:
            self.movement_manager.stop()

        if self.audio:
            self.audio.stop()

        logger.info("[CLEANUP] Shutdown complete")

    async def process_voice_input(self, text: str) -> None:
        """Process voice input through the full pipeline."""
        print(f"\n[INPUT] {text}")

        result = await self.brain.query(text)
        print(f"[RESULT] reply: {result.reply}")
        print(f"[RESULT] command: {result.device_command}")

        in_sleep_mode = self.light_actions.movement_manager.is_sleep_mode()

        if in_sleep_mode and result.device_command != "Light_ON":
            logger.info("[SLEEP] In sleep mode, ignoring non-Light_ON command")
            return

        if result.reply and not result.reply.startswith("["):
            logger.info(f"[TTS] Speaking: {result.reply}")
            tts_file = self.tts.speak_sync(result.reply)
            if tts_file:
                audio.play_tts_audio(tts_file)
            else:
                logger.warning("[TTS] TTS file not generated")

        await network.send_tcp_command(
            result.device_command,
            config.XIAO_CONFIG["ip"],
            config.XIAO_CONFIG["port"]
        )

        asyncio.create_task(self.light_actions.do_light_action(result.device_command))


async def voice_mode_main() -> None:
    """Main voice interaction loop."""
    system = ReachyMotorSystem()
    await system.initialize()

    retry_count = 0
    max_retries = 3
    retry_delay = 3.0

    try:
        while retry_count < max_retries:
            asr_client = asr.DoubaoASR()
            try:
                await asr_client.connect()
            except (ConnectionResetError, OSError) as e:
                logger.warning(f"[ASR] Connection failed: {e}, retry {retry_count+1}/{max_retries}")
                retry_count += 1
                await asyncio.sleep(retry_delay)
                continue

            print("\n[VOICE] 请说话...")
            speech_buffer = []
            total_bytes = 0

            start_time = time.time()
            deadline = start_time + 5.0
            speech_detected = False
            silence_after_speech = 0

            while time.time() < deadline:
                chunk = system.audio.read_chunk(0.01)
                if chunk:
                    total_bytes += len(chunk)
                    chunk_count = len(chunk)
                    max_val = max(
                        abs(int.from_bytes(chunk[i:i+2], 'little', signed=True))
                        for i in range(0, min(len(chunk), 100), 2)
                    )
                    is_speech = max_val > 500

                    if is_speech:
                        speech_detected = True
                        silence_after_speech = 0
                        speech_buffer.append(chunk)
                    elif speech_detected:
                        silence_after_speech += 1
                        if silence_after_speech < 20:
                            speech_buffer.append(chunk)
                        elif len(speech_buffer) > 20:
                            break
                await asyncio.sleep(0)

            elapsed = time.time() - start_time
            total_audio_bytes = sum(len(c) for c in speech_buffer)
            logger.info(f"[ASR] Captured {len(speech_buffer)} chunks, {total_audio_bytes} bytes in {elapsed:.1f}s")

            if len(speech_buffer) < 20:
                logger.warning("[ASR] No speech detected, retrying...")
                await asr_client.close()
                retry_count += 1
                await asyncio.sleep(retry_delay)
                continue

            full_audio = b"".join(speech_buffer)
            logger.info(f"[ASR] Sending {len(full_audio)} bytes of audio ({len(full_audio)/16000/2:.1f}s)")
            await asr_client.send_audio(full_audio, is_last=True)
            await asyncio.sleep(0.5)

            full_text = ""
            while True:
                text = await asr_client.get_text(timeout=3.0)
                if text is None:
                    break
                if text.strip():
                    full_text = text.strip()
                    logger.info(f"[ASR] Final: {full_text}")

            await asr_client.close()

            if full_text:
                await system.process_voice_input(full_text)

            retry_count = 0
            await asyncio.sleep(1.0)

    except KeyboardInterrupt:
        print("\n\n正在退出...")
    finally:
        await system.cleanup()


async def main() -> None:
    """Main entry point."""
    await voice_mode_main()


if __name__ == "__main__":
    asyncio.run(main())
