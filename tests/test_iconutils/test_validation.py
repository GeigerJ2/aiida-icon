"""Tests for ICON configuration validation."""

import textwrap

import f90nml

from aiida_icon.iconutils import validation


class TestValidateIconConfiguration:
    """Test suite for validate_icon_configuration function."""

    def test_valid_configuration_no_warnings(self):
        """Test that a valid configuration produces no warnings."""
        master_nml = f90nml.reads(
            textwrap.dedent("""
            &master_time_control_nml
             experimentStartDate  = '2000-01-01T00:00:00Z'
             experimentStopDate   = '2000-01-01T01:00:00Z'
             checkpointTimeIntval = 'PT1M'
             restartTimeIntval    = 'PT1M'
            /
            """)
        )

        model_nml = f90nml.reads(
            textwrap.dedent("""
            &run_nml
             dtime = 60
            /
            &output_nml
             output_start    = '2000-01-01T00:00:00Z'
             output_end      = '2000-01-01T01:00:00Z'
             output_filename = 'test'
            /
            """)
        )

        warnings = validation.validate_icon_configuration(master_nml, model_nml)
        assert len(warnings) == 0

    def test_checkpoint_larger_than_duration(self):
        """Test warning when checkpoint interval exceeds experiment duration."""
        master_nml = f90nml.reads(
            textwrap.dedent("""
            &master_time_control_nml
             experimentStartDate  = '2000-01-01T00:00:00Z'
             experimentStopDate   = '2000-01-01T00:01:00Z'
             checkpointTimeIntval = 'PT2M'
            /
            """)
        )

        model_nml = f90nml.reads("&run_nml\n/")

        warnings = validation.validate_icon_configuration(master_nml, model_nml)
        assert len(warnings) == 1
        assert "checkpointTimeIntval" in warnings[0]
        assert "larger than experiment duration" in warnings[0]
        assert "No checkpoints will be written" in warnings[0]

    def test_restart_larger_than_duration(self):
        """Test warning when restart interval exceeds experiment duration."""
        master_nml = f90nml.reads(
            textwrap.dedent("""
            &master_time_control_nml
             experimentStartDate  = '2000-01-01T00:00:00Z'
             experimentStopDate   = '2000-01-01T00:01:00Z'
             restartTimeIntval    = 'PT2M'
            /
            """)
        )

        model_nml = f90nml.reads("&run_nml\n/")

        warnings = validation.validate_icon_configuration(master_nml, model_nml)
        assert len(warnings) == 1
        assert "restartTimeIntval" in warnings[0]
        assert "larger than experiment duration" in warnings[0]

    def test_checkpoint_restart_mismatch(self):
        """Test warning when checkpoint and restart intervals don't match."""
        master_nml = f90nml.reads(
            textwrap.dedent("""
            &master_time_control_nml
             experimentStartDate  = '2000-01-01T00:00:00Z'
             experimentStopDate   = '2000-01-01T01:00:00Z'
             checkpointTimeIntval = 'PT1M'
             restartTimeIntval    = 'PT2M'
            /
            """)
        )

        model_nml = f90nml.reads("&run_nml\n/")

        warnings = validation.validate_icon_configuration(master_nml, model_nml)
        assert any("don't match" in w for w in warnings)
        assert any("cycling workflows" in w for w in warnings)

    def test_dtime_larger_than_duration(self):
        """Test warning when model timestep exceeds experiment duration.

        This was the actual bug in aquaplanet: dtime=300s but 30s chunks.
        """
        master_nml = f90nml.reads(
            textwrap.dedent("""
            &master_time_control_nml
             experimentStartDate  = '2000-01-01T00:00:00Z'
             experimentStopDate   = '2000-01-01T00:00:30Z'
            /
            """)
        )

        model_nml = f90nml.reads(
            textwrap.dedent("""
            &run_nml
             dtime = 300
            /
            """)
        )

        warnings = validation.validate_icon_configuration(master_nml, model_nml)
        assert any("dtime" in w for w in warnings)
        assert any("cannot complete even one timestep" in w for w in warnings)

    def test_dtime_more_than_half_duration(self):
        """Test warning when dtime is very large relative to duration."""
        master_nml = f90nml.reads(
            textwrap.dedent("""
            &master_time_control_nml
             experimentStartDate  = '2000-01-01T00:00:00Z'
             experimentStopDate   = '2000-01-01T00:01:00Z'
            /
            """)
        )

        model_nml = f90nml.reads(
            textwrap.dedent("""
            &run_nml
             dtime = 40
            /
            """)
        )

        warnings = validation.validate_icon_configuration(master_nml, model_nml)
        assert any("more than half" in w for w in warnings)

    def test_output_end_before_experiment_start(self):
        """Test warning when output window is completely before experiment."""
        master_nml = f90nml.reads(
            textwrap.dedent("""
            &master_time_control_nml
             experimentStartDate  = '2000-01-01T01:00:00Z'
             experimentStopDate   = '2000-01-01T02:00:00Z'
            /
            """)
        )

        model_nml = f90nml.reads(
            textwrap.dedent("""
            &run_nml
             dtime = 60
            /
            &output_nml
             output_start    = '2000-01-01T00:00:00Z'
             output_end      = '2000-01-01T00:30:00Z'
             output_filename = 'test'
            /
            """)
        )

        warnings = validation.validate_icon_configuration(master_nml, model_nml)
        assert any("output_end" in w and "before experimentStartDate" in w for w in warnings)
        assert any("No output will be written" in w for w in warnings)

    def test_output_start_after_experiment_stop(self):
        """Test warning when output window is completely after experiment."""
        master_nml = f90nml.reads(
            textwrap.dedent("""
            &master_time_control_nml
             experimentStartDate  = '2000-01-01T00:00:00Z'
             experimentStopDate   = '2000-01-01T01:00:00Z'
            /
            """)
        )

        model_nml = f90nml.reads(
            textwrap.dedent("""
            &run_nml
             dtime = 60
            /
            &output_nml
             output_start    = '2000-01-01T02:00:00Z'
             output_end      = '2000-01-01T03:00:00Z'
             output_filename = 'test'
            /
            """)
        )

        warnings = validation.validate_icon_configuration(master_nml, model_nml)
        assert any("output_start" in w and "after experimentStopDate" in w for w in warnings)
        assert any("No output will be written" in w for w in warnings)

    def test_output_end_before_experiment_stop(self):
        """Test warning when output ends before experiment ends.

        This was the actual bug in aquaplanet cycles 2 and 3:
        output_end was 00:01:00 but experiment ran to 00:03:00.
        """
        master_nml = f90nml.reads(
            textwrap.dedent("""
            &master_time_control_nml
             experimentStartDate  = '2000-01-01T00:00:00Z'
             experimentStopDate   = '2000-01-01T00:03:00Z'
            /
            """)
        )

        model_nml = f90nml.reads(
            textwrap.dedent("""
            &run_nml
             dtime = 2
            /
            &output_nml
             output_start    = '2000-01-01T00:00:00Z'
             output_end      = '2000-01-01T00:01:00Z'
             output_filename = './atm_2d/'
            /
            """)
        )

        warnings = validation.validate_icon_configuration(master_nml, model_nml)
        assert any("output_end" in w and "before experimentStopDate" in w for w in warnings)
        assert any("Final timesteps will not be written" in w for w in warnings)

    def test_multiple_output_streams(self):
        """Test validation with multiple output_nml sections."""
        master_nml = f90nml.reads(
            textwrap.dedent("""
            &master_time_control_nml
             experimentStartDate  = '2000-01-01T00:00:00Z'
             experimentStopDate   = '2000-01-01T01:00:00Z'
            /
            """)
        )

        model_nml = f90nml.reads(
            textwrap.dedent("""
            &run_nml
             dtime = 60
            /
            &output_nml
             output_start    = '2000-01-01T00:00:00Z'
             output_end      = '2000-01-01T01:00:00Z'
             output_filename = 'stream1'
            /
            &output_nml
             output_start    = '2000-01-01T00:00:00Z'
             output_end      = '2000-01-01T00:30:00Z'
             output_filename = 'stream2'
            /
            """)
        )

        warnings = validation.validate_icon_configuration(master_nml, model_nml)
        # stream2 ends before experiment ends
        assert any("stream2" in w and "before experimentStopDate" in w for w in warnings)

    def test_stop_before_start(self):
        """Test error when stop is before start."""
        master_nml = f90nml.reads(
            textwrap.dedent("""
            &master_time_control_nml
             experimentStartDate  = '2000-01-01T01:00:00Z'
             experimentStopDate   = '2000-01-01T00:00:00Z'
            /
            """)
        )

        model_nml = f90nml.reads("&run_nml\n/")

        warnings = validation.validate_icon_configuration(master_nml, model_nml)
        assert any("not after experimentStartDate" in w for w in warnings)

    def test_missing_master_time_control(self):
        """Test graceful handling when master_time_control_nml is missing."""
        master_nml = f90nml.reads("&master_nml\n/")
        model_nml = f90nml.reads("&run_nml\n/")

        warnings = validation.validate_icon_configuration(master_nml, model_nml)
        assert len(warnings) == 0  # Should not crash, just skip validation

    def test_checkpoint_not_evenly_divisible(self):
        """Test warning when checkpoint doesn't evenly divide duration."""
        master_nml = f90nml.reads(
            textwrap.dedent("""
            &master_time_control_nml
             experimentStartDate  = '2000-01-01T00:00:00Z'
             experimentStopDate   = '2000-01-01T01:00:00Z'
             checkpointTimeIntval = 'PT25M'
            /
            """)
        )

        model_nml = f90nml.reads("&run_nml\n/")

        warnings = validation.validate_icon_configuration(master_nml, model_nml)
        assert any("does not evenly divide" in w for w in warnings)

    def test_realistic_cycling_configuration(self):
        """Test a realistic cycling workflow configuration (1-minute cycles)."""
        master_nml = f90nml.reads(
            textwrap.dedent("""
            &master_time_control_nml
             experimentStartDate  = '2000-01-01T00:00:00Z'
             experimentStopDate   = '2000-01-01T00:01:00Z'
             checkpointTimeIntval = 'PT1M'
             restartTimeIntval    = 'PT1M'
            /
            """)
        )

        model_nml = f90nml.reads(
            textwrap.dedent("""
            &run_nml
             dtime = 2
            /
            &output_nml
             output_start    = '2000-01-01T00:00:03Z'
             output_end      = '2000-01-01T00:01:00Z'
             output_filename = './atm_2d/'
            /
            """)
        )

        warnings = validation.validate_icon_configuration(master_nml, model_nml)
        assert len(warnings) == 0  # This is the fixed aquaplanet config

    def test_realistic_longterm_configuration(self):
        """Test a realistic long-term configuration (2-month cycles)."""
        master_nml = f90nml.reads(
            textwrap.dedent("""
            &master_time_control_nml
             experimentStartDate  = '2026-01-01T00:00:00Z'
             experimentStopDate   = '2026-03-01T00:00:00Z'
             checkpointTimeIntval = 'P2M'
             restartTimeIntval    = 'P2M'
            /
            """)
        )

        model_nml = f90nml.reads(
            textwrap.dedent("""
            &run_nml
             dtime = 1209600
            /
            """)
        )

        warnings = validation.validate_icon_configuration(master_nml, model_nml)
        assert len(warnings) == 0  # This is the fixed small-icon config
