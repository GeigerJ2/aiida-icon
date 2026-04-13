"""Validation functions for ICON configuration sanity checks."""

from __future__ import annotations

import typing
from datetime import datetime

import isodate  # type: ignore[import-not-found]

from aiida_icon.iconutils import namelists

if typing.TYPE_CHECKING:
    import logging

# Tolerance for floating point comparisons (seconds)
_DURATION_TOLERANCE = 1e-6


def validate_icon_configuration(
    master_nml: namelists.NMLInput,
    model_nml: namelists.NMLInput,
    logger: logging.Logger | None = None,
) -> list[str]:
    """Validate ICON namelist configuration for common issues.

    Catches configuration problems that would cause ICON to fail or produce
    unexpected results, such as:
    - Checkpoint/restart intervals larger than experiment duration
    - Model timestep (dtime) too large for experiment duration
    - Output windows outside experiment time range
    - Mismatched checkpoint and restart intervals (important for cycling)

    Args:
        master_nml: Master namelist data
        model_nml: Model namelist data
        logger: Optional logger for warnings

    Returns:
        List of warning messages (empty if no issues found)
    """
    warnings: list[str] = []
    master_data = namelists.namelists_data(master_nml)
    model_data = namelists.namelists_data(model_nml)

    # Extract timing from master_time_control_nml
    if "master_time_control_nml" not in master_data:
        return warnings  # Can't validate without timing info

    time_control = master_data["master_time_control_nml"]

    try:
        start_str = time_control.get("experimentstartdate", "")
        stop_str = time_control.get("experimentstopdate", "")
        checkpoint_str = time_control.get("checkpointtimeintval", "")
        restart_str = time_control.get("restarttimeintval", "")

        # Parse dates
        if not start_str or not stop_str:
            return warnings  # Can't validate without start/stop

        start = datetime.fromisoformat(start_str.rstrip("Z"))
        stop = datetime.fromisoformat(stop_str.rstrip("Z"))
        duration = stop - start
        duration_seconds = duration.total_seconds()

        if duration_seconds <= 0:
            warnings.append(f"experimentStopDate ({stop_str}) is not after experimentStartDate ({start_str})")
            return warnings  # Can't validate further

        # Check 1: Checkpoint interval validation
        if checkpoint_str:
            try:
                checkpoint_td = isodate.parse_duration(checkpoint_str)
                checkpoint_seconds = checkpoint_td.total_seconds()

                if checkpoint_seconds > duration_seconds:
                    warnings.append(
                        f"checkpointTimeIntval ({checkpoint_str} = {checkpoint_seconds}s) is larger than "
                        f"experiment duration ({duration_seconds}s). No checkpoints will be written!"
                    )
                elif checkpoint_seconds == duration_seconds:
                    # This is OK - writes one checkpoint at the end
                    pass
                # Multiple checkpoints - warn if not evenly divisible
                elif duration_seconds % checkpoint_seconds > _DURATION_TOLERANCE:
                    warnings.append(
                        f"checkpointTimeIntval ({checkpoint_str}) does not evenly divide experiment duration. "
                        f"Last checkpoint may be at unexpected time."
                    )
            except (ValueError, isodate.ISO8601Error):
                warnings.append(f"Could not parse checkpointTimeIntval: {checkpoint_str}")

        # Check 2: Restart interval validation
        if restart_str:
            try:
                restart_td = isodate.parse_duration(restart_str)
                restart_seconds = restart_td.total_seconds()

                if restart_seconds > duration_seconds:
                    warnings.append(
                        f"restartTimeIntval ({restart_str} = {restart_seconds}s) is larger than "
                        f"experiment duration ({duration_seconds}s)"
                    )

                # Check if checkpoint and restart intervals match
                if checkpoint_str and restart_str:
                    checkpoint_td = isodate.parse_duration(checkpoint_str)
                    if abs(checkpoint_td.total_seconds() - restart_seconds) > _DURATION_TOLERANCE:
                        warnings.append(
                            f"checkpointTimeIntval ({checkpoint_str}) and restartTimeIntval ({restart_str}) "
                            f"don't match. For cycling workflows, these should be equal to the cycle period."
                        )
            except (ValueError, isodate.ISO8601Error):
                warnings.append(f"Could not parse restartTimeIntval: {restart_str}")

        # Check 3: Model timestep (dtime) validation
        if "run_nml" in model_data:
            dtime = model_data["run_nml"].get("dtime")
            if dtime and isinstance(dtime, (int, float)):
                if dtime > duration_seconds:
                    warnings.append(
                        f"Model timestep dtime ({dtime}s) is larger than experiment duration ({duration_seconds}s). "
                        f"ICON cannot complete even one timestep!"
                    )
                elif dtime > duration_seconds / 2:
                    warnings.append(
                        f"Model timestep dtime ({dtime}s) is more than half the experiment duration ({duration_seconds}s). "
                        f"This may cause issues or produce minimal output."
                    )

        # Check 4: Output window validation
        if "output_nml" in model_data:
            # Handle both single output_nml and list of output_nml
            output_nmls = model_data["output_nml"]
            if not isinstance(output_nmls, list):
                output_nmls = [output_nmls]

            for i, output_nml in enumerate(output_nmls):
                output_start_str = output_nml.get("output_start", "")
                output_end_str = output_nml.get("output_end", "")
                output_filename = output_nml.get("output_filename", f"stream_{i}")

                if output_start_str and output_end_str:
                    try:
                        output_start = datetime.fromisoformat(output_start_str.rstrip("Z"))
                        output_end = datetime.fromisoformat(output_end_str.rstrip("Z"))

                        # Warn if output window doesn't overlap with experiment
                        if output_end <= start:
                            warnings.append(
                                f"Output stream '{output_filename}': output_end ({output_end_str}) is before "
                                f"experimentStartDate ({start_str}). No output will be written!"
                            )
                        elif output_start >= stop:
                            warnings.append(
                                f"Output stream '{output_filename}': output_start ({output_start_str}) is after "
                                f"experimentStopDate ({stop_str}). No output will be written!"
                            )
                        elif output_end < stop:
                            warnings.append(
                                f"Output stream '{output_filename}': output_end ({output_end_str}) is before "
                                f"experimentStopDate ({stop_str}). Final timesteps will not be written."
                            )
                    except (ValueError, AttributeError):
                        # Can't parse dates, skip validation
                        pass

    except (ValueError, AttributeError, KeyError, TypeError) as e:
        # Don't fail the calculation on validation errors, just log
        if logger:
            logger.warning("Error during configuration validation: %s", e)

    # Log all warnings
    if logger:
        for warning in warnings:
            logger.warning("Configuration validation: %s", warning)

    return warnings
