##############################
 GitLab Environment Variables
##############################

*********************************
 Available Environment Variables
*********************************

This page lists the environment variables used by idf-ci when integrating with GitLab. You can set them in your shell environment or in ``.idf_ci.toml`` where supported by the GitLab settings.

Supported environment variables are read when idf-ci uses them. If a supported value changes between commands in the same process, the next command uses the new value.

.. autopydantic_settings:: idf_ci.envs.GitlabEnvVars
