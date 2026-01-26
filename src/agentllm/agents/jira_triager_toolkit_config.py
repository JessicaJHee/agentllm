"""Jira Triager configuration manager."""

import json
import os

from loguru import logger

from agentllm.agents.toolkit_configs.base import BaseToolkitConfig
from agentllm.tools.jira_triager_toolkit import JiraTriagerTools


class JiraTriagerToolkitConfig(BaseToolkitConfig):
    """Manages Jira Triager toolkit configuration.

    Loads configuration from:
    - Local file (JIRA_TRIAGER_CONFIG_FILE env var or local_config_file parameter), OR
    - Google Drive folder (rhdh-teams.json, jira-filter.txt)

    Requires:
    - Jira credentials (always)
    - Local config file OR Google Drive OAuth
    """

    def __init__(
        self,
        token_storage=None,
        gdrive_folder_id: str | None = None,
        local_config_file: str | None = None,
    ):
        """Initialize Jira Triager configuration.

        Args:
            token_storage: TokenStorage instance for database-backed credentials
            gdrive_folder_id: Google Drive folder ID containing config files (overrides env var)
            local_config_file: Local file path to rhdh-teams.json (for automation mode)
        """
        super().__init__(token_storage)

        # Check for local config file (takes precedence over Google Drive)
        if local_config_file is None:
            local_config_file = os.getenv("JIRA_TRIAGER_CONFIG_FILE")

        self._local_config_file = local_config_file

        # Set default Google Drive folder ID (only used if no local config)
        if gdrive_folder_id is None:
            gdrive_folder_id = os.getenv("JIRA_TRIAGER_GDRIVE_FOLDER_ID")

        self._gdrive_folder_id = gdrive_folder_id

        # Configuration loaded from file or Google Drive (cached per user)
        self._user_configs: dict[str, dict] = {}  # user_id -> config dict

        # Store per-user Jira Triager toolkits (in-memory cache)
        self._triager_toolkits: dict[str, JiraTriagerTools] = {}

        if self._local_config_file:
            logger.info(f"JiraTriagerToolkitConfig: Using local config file: {self._local_config_file}")
        elif self._gdrive_folder_id:
            logger.info(f"JiraTriagerToolkitConfig: Using Google Drive folder: {self._gdrive_folder_id}")
        else:
            logger.warning("JiraTriagerToolkitConfig: No config source configured (no local file or GDrive folder ID)")

    def is_configured(self, user_id: str) -> bool:
        """Check if Jira Triager is configured for user.

        Jira Triager is configured if:
        - Automation mode: Local config file exists (Jira credentials from env), OR
        - Interactive mode: Google Drive configured and Jira credentials in database

        Args:
            user_id: User identifier

        Returns:
            True if user has valid configuration
        """
        # Local config file mode (automation) - no token storage needed
        if self._local_config_file and os.path.exists(self._local_config_file):
            logger.debug(f"JiraTriagerToolkitConfig: is_configured=True (local file mode)")
            return True

        # Google Drive mode (interactive) - requires token storage
        if not self.token_storage:
            logger.debug("JiraTriagerToolkitConfig: is_configured=False (no token_storage)")
            return False

        # Check if user has Jira credentials (always required in Google Drive mode)
        has_jira = self.token_storage.get_token("jira", user_id) is not None
        if not has_jira:
            logger.debug("JiraTriagerToolkitConfig: is_configured=False (no Jira token)")
            return False

        # Check for Google Drive credentials
        has_gdrive = self.token_storage.get_token("gdrive", user_id) is not None
        logger.debug(f"JiraTriagerToolkitConfig: is_configured={has_gdrive} (Google Drive mode)")
        return has_gdrive

    def extract_and_store_config(self, message: str, user_id: str) -> str | None:
        """Extract and store configuration from user message.

        This config doesn't have its own configuration to extract - it depends
        on JiraConfig. Returns None to let JiraConfig handle extraction.

        Args:
            message: User message
            user_id: User identifier

        Returns:
            None (no configuration to extract)
        """
        return None

    def get_config_prompt(self, user_id: str) -> str | None:
        """Get configuration prompt if needed.

        JiraTriagerConfig doesn't provide its own prompts - it depends on
        JiraConfig and GoogleDriveConfig which handle their own prompts.

        Args:
            user_id: User identifier

        Returns:
            None (this config doesn't prompt directly)
        """
        return None

    def get_toolkit(self, user_id: str) -> JiraTriagerTools | None:
        """Get Jira Triager toolkit for user if configured.

        Works in two modes:
        - Automation: Local config file + JIRA_API_TOKEN from environment
        - Interactive: Google Drive config + Jira token from database

        Args:
            user_id: User identifier

        Returns:
            JiraTriagerTools instance if configured, None otherwise
        """
        # Return cached toolkit if available
        if user_id in self._triager_toolkits:
            return self._triager_toolkits[user_id]

        # If not configured, return None
        if not self.is_configured(user_id):
            return None

        # Load configuration if not already loaded
        if user_id not in self._user_configs:
            # Try local file first, then fall back to Google Drive
            if self._local_config_file and os.path.exists(self._local_config_file):
                config = self._load_configuration_from_file(user_id)
                if not config:
                    logger.error(f"Failed to load configuration from local file for user {user_id}")
                    return None
            else:
                config = self._load_configuration_from_gdrive(user_id)
                if not config:
                    logger.error(f"Failed to load configuration from Google Drive for user {user_id}")
                    return None
            self._user_configs[user_id] = config

        # Get Jira credentials - from environment (automation) or token storage (interactive)
        try:
            # Automation mode: Get credentials from environment variables
            if not self.token_storage:
                jira_token_str = os.getenv("JIRA_API_TOKEN")
                jira_server = os.getenv("JIRA_SERVER_URL", "https://issues.redhat.com")
                if not jira_token_str:
                    logger.error("No JIRA_API_TOKEN found in environment (automation mode)")
                    return None
                token_data = {"token": jira_token_str, "server_url": jira_server}
                logger.info(f"Using JIRA_API_TOKEN from environment for user {user_id}")
            # Interactive mode: Get credentials from token storage
            else:
                token_data = self.token_storage.get_token("jira", user_id)
                if not token_data:
                    logger.error(f"No Jira token found for user {user_id}")
                    return None

            # Create the triager toolkit (logic-based, no RAG dependencies)
            toolkit = JiraTriagerTools(
                jira_token=token_data["token"],
                jira_url=token_data["server_url"],
            )

            # Cache the toolkit
            self._triager_toolkits[user_id] = toolkit
            logger.info(f"Created JiraTriagerTools for user {user_id}")

            return toolkit

        except Exception as e:
            logger.error(f"Failed to create JiraTriagerTools for user {user_id}: {e}")
            return None

    def check_authorization_request(self, message: str, user_id: str) -> str | None:
        """Check if message requests Jira Triager access and prompt if needed.

        Since this depends on JiraConfig, delegate authorization checks to it.

        Args:
            message: User message
            user_id: User identifier

        Returns:
            Configuration prompt if needed, None otherwise
        """
        # Check if message mentions triage-related keywords
        triage_keywords = [
            "triage",
            "triag",
            "assign",
            "team",
            "component",
        ]

        message_lower = message.lower()
        mentions_triage = any(keyword in message_lower for keyword in triage_keywords)

        if not mentions_triage:
            return None

        # Check if configured (which checks JiraConfig)
        if self.is_configured(user_id):
            logger.info(f"User {user_id} has Jira Triager access")
            return None

        # Delegate to JiraConfig for the prompt
        return self._jira_config.get_config_prompt(user_id)

    def requires_agent_recreation(self, config_name: str) -> bool:
        """Check if this config requires agent recreation.

        Jira Triager configuration adds new tools to the agent.

        Args:
            config_name: Configuration name

        Returns:
            Always True since triager tools need to be added
        """
        return True

    def is_required(self) -> bool:
        """Check if this toolkit is required.

        Returns:
            True - Jira Triager toolkit is required for the agent
        """
        return True

    def get_agent_instructions(self, user_id: str) -> list[str]:
        """Get Jira Triager-specific agent instructions.

        Args:
            user_id: User identifier

        Returns:
            List of instruction strings
        """
        if not self.get_toolkit(user_id):
            return []

        instructions = [
            "TRIAGE DECISION ALGORITHM:",
            "",
            "1. COMPONENT ANALYSIS (Primary):",
            "   - Check COMPONENT_TEAM_MAP for ticket components",
            "   - Specific components override general ones",
            "   - Clear mapping → 85-90% confidence baseline",
            "   - CRITICAL: Validate recommended components against allowed_components from triage_ticket",
            "   - Only recommend components that exist in allowed_components list",
            "",
            "2. KEYWORD ANALYSIS (Secondary):",
            "   Security Team keywords: keycloak, oauth, oidc, rbac, authentication",
            "   Install Team keywords: operator, helm, deployment, kubernetes",
            "   Frontend Team keywords: scaffolder, template, UI, react, theme",
            "   Backend Team keywords: backend, API, service, database, performance",
            "",
            "3. ASSIGNEE VALIDATION (Tertiary):",
            "   - Check TEAM_ASSIGNEE_MAP",
            "   - Matching assignee → +5% confidence",
            "",
            "See external system prompt (Google Doc) for detailed triage guidelines.",
        ]

        # Add configuration from Google Drive if loaded
        config = self._user_configs.get(user_id)
        if config:
            instructions.append("")
            instructions.append("CONFIGURATION (loaded from Google Drive):")

            if "allowed_teams" in config:
                instructions.append("")
                instructions.append("ALLOWED_TEAMS:")
                instructions.append("```json")
                instructions.append(json.dumps(config["allowed_teams"], indent=2))
                instructions.append("```")

            if "component_team_map" in config:
                instructions.append("")
                instructions.append("COMPONENT_TEAM_MAP:")
                instructions.append("```json")
                instructions.append(json.dumps(config["component_team_map"], indent=2))
                instructions.append("```")

            if "team_id_map" in config:
                instructions.append("")
                instructions.append("TEAM_ID_MAP (Jira Team Field IDs):")
                instructions.append("```json")
                instructions.append(json.dumps(config["team_id_map"], indent=2))
                instructions.append("```")
                instructions.append("Use these team IDs when updating Jira ticket 'Team' fields.")

            if "team_assignee_map" in config:
                instructions.append("")
                instructions.append("TEAM_ASSIGNEE_MAP:")
                instructions.append("```json")
                instructions.append(json.dumps(config["team_assignee_map"], indent=2))
                instructions.append("```")

            if "jira_filter" in config:
                instructions.append("")
                instructions.append(f"DEFAULT_JQL_FILTER: {config['jira_filter']}")

        return instructions

    def _load_configuration_from_file(self, user_id: str) -> dict | None:
        """Load configuration from local file.

        Loads configuration from the local rhdh-teams.json file specified by
        JIRA_TRIAGER_CONFIG_FILE environment variable or local_config_file parameter.

        The rhdh-teams.json file has the structure:
        {
          "Team Name": {
            "id": "jira_team_id",
            "components": ["Component1", "Component2"],
            "members": ["Member1", "Member2"]
          }
        }

        This is transformed into:
        - team_id_map: {"Team Name": "jira_team_id"}
        - component_team_map: {"Team Name": ["Component1", "Component2"]}
        - team_assignee_map: {"Team Name": ["Member1", "Member2"]}
        - allowed_teams: list of team names

        Args:
            user_id: User identifier

        Returns:
            Configuration dictionary, or None if loading fails
        """
        if not self._local_config_file:
            logger.error("Local config file not set")
            return None

        if not os.path.exists(self._local_config_file):
            logger.error(f"Local config file not found: {self._local_config_file}")
            return None

        try:
            logger.info(f"Loading Jira Triager configuration from local file: {self._local_config_file}")

            with open(self._local_config_file, encoding="utf-8") as f:
                teams_data = json.load(f)

            logger.info(f"Loaded rhdh-teams.json from local file with {len(teams_data)} teams")

            # Transform consolidated format into individual maps (same as Google Drive version)
            config = {}
            config["team_id_map"] = {}
            config["component_team_map"] = {}
            config["team_assignee_map"] = {}

            for team_name, team_data in teams_data.items():
                # Extract team ID (required)
                if "id" in team_data:
                    config["team_id_map"][team_name] = team_data["id"]

                # Extract components (optional)
                if "components" in team_data and team_data["components"]:
                    config["component_team_map"][team_name] = team_data["components"]

                # Extract members (optional)
                if "members" in team_data and team_data["members"]:
                    config["team_assignee_map"][team_name] = team_data["members"]

            # Derive allowed_teams from team names
            config["allowed_teams"] = list(config["team_id_map"].keys())
            logger.info(f"Derived allowed_teams from rhdh-teams.json: {len(config['allowed_teams'])} teams")
            logger.info(f"Loaded {len(config['component_team_map'])} teams with components")
            logger.info(f"Loaded {len(config['team_assignee_map'])} teams with members")

            # Note: jira_filter is not loaded from local file - agent will use default
            # (could be extended to load from separate jira-filter.txt file if needed)

            if not config or "team_id_map" not in config:
                logger.error("No valid configuration loaded from local file")
                return None

            logger.info(f"Successfully loaded configuration from local file: {list(config.keys())}")
            return config

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse {self._local_config_file}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading configuration from local file: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return None

    def _load_configuration_from_gdrive(self, user_id: str) -> dict | None:
        """Load all configuration from Google Drive folder.

        Fetches configuration from the configured Google Drive folder:
        - rhdh-teams.json (consolidated team configuration)
        - jira-filter.txt (default JQL filter)

        The rhdh-teams.json file has the structure:
        {
          "Team Name": {
            "id": "jira_team_id",
            "components": ["Component1", "Component2"],
            "members": ["Member1", "Member2"]
          }
        }

        This is transformed into:
        - team_id_map: {"Team Name": "jira_team_id"}
        - component_team_map: {"Team Name": ["Component1", "Component2"]}
        - team_assignee_map: {"Team Name": ["Member1", "Member2"]}
        - allowed_teams: list of team names

        Args:
            user_id: User identifier

        Returns:
            Configuration dictionary, or None if loading fails
        """
        if not self._gdrive_folder_id:
            logger.error("JIRA_TRIAGER_GDRIVE_FOLDER_ID not set. Cannot load configuration.")
            return None

        if not self.token_storage:
            logger.error("Token storage not available")
            return None

        # Get Google Drive credentials from token storage
        gdrive_creds = self.token_storage.get_token("gdrive", user_id)
        if not gdrive_creds:
            logger.error(f"Google Drive not configured for user {user_id}")
            return None

        try:
            # Create Google Drive toolkit from credentials
            from agentllm.tools.gdrive_toolkit import GoogleDriveTools

            gdrive_toolkit = GoogleDriveTools(credentials=gdrive_creds)

            logger.info(f"Loading Jira Triager configuration from Google Drive folder {self._gdrive_folder_id}")

            config = {}

            # Fetch consolidated teams configuration
            try:
                teams_content = self._fetch_file_from_gdrive(user_id, gdrive_toolkit, "rhdh-teams.json")
                if not teams_content:
                    logger.error("Could not load rhdh-teams.json from Google Drive")
                    return None

                teams_data = json.loads(teams_content)
                logger.info(f"Loaded rhdh-teams.json from Google Drive with {len(teams_data)} teams")

                # Transform consolidated format into individual maps
                config["team_id_map"] = {}
                config["component_team_map"] = {}
                config["team_assignee_map"] = {}

                for team_name, team_data in teams_data.items():
                    # Extract team ID (required)
                    if "id" in team_data:
                        config["team_id_map"][team_name] = team_data["id"]

                    # Extract components (optional)
                    if "components" in team_data and team_data["components"]:
                        config["component_team_map"][team_name] = team_data["components"]

                    # Extract members (optional)
                    if "members" in team_data and team_data["members"]:
                        config["team_assignee_map"][team_name] = team_data["members"]

                # Derive allowed_teams from team names
                config["allowed_teams"] = list(config["team_id_map"].keys())
                logger.info(f"Derived allowed_teams from rhdh-teams.json: {len(config['allowed_teams'])} teams")
                logger.info(f"Loaded {len(config['component_team_map'])} teams with components")
                logger.info(f"Loaded {len(config['team_assignee_map'])} teams with members")

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse rhdh-teams.json: {e}")
                return None
            except Exception as e:
                logger.error(f"Error loading rhdh-teams.json: {e}")
                return None

            # Fetch JQL filter (text file)
            try:
                filter_content = self._fetch_file_from_gdrive(user_id, gdrive_toolkit, "jira-filter.txt")
                if filter_content:
                    config["jira_filter"] = filter_content.strip()
                    logger.info("Loaded jira_filter from Google Drive: jira-filter.txt")
            except Exception as e:
                logger.error(f"Error loading jira-filter.txt: {e}")

            if not config or "team_id_map" not in config:
                logger.error("No valid configuration loaded from Google Drive")
                return None

            logger.info(f"Successfully loaded configuration from Google Drive: {list(config.keys())}")
            return config

        except Exception as e:
            logger.error(f"Failed to load configuration from Google Drive: {e}")
            return None

    def _fetch_file_from_gdrive(self, _user_id: str, gdrive_toolkit, file_path: str) -> str | None:
        """Fetch a file from Google Drive folder.

        Args:
            user_id: User identifier
            gdrive_toolkit: Google Drive toolkit instance
            file_path: Filename in the folder (e.g., "component-team.json", "jira-filter.txt")

        Returns:
            File content as string, or None if fetch fails
        """
        try:
            # Get the Google Drive exporter from the toolkit
            exporter = gdrive_toolkit.exporter
            drive_service = exporter.service

            # The file is directly in the root folder (no subfolders)
            filename = file_path

            # Search for the file in the configured folder
            query = f"name='{filename}' and '{self._gdrive_folder_id}' in parents and trashed=false"

            results = drive_service.files().list(q=query, fields="files(id, name, mimeType)", supportsAllDrives=True).execute()

            files = results.get("files", [])

            if not files:
                logger.error(f"File '{filename}' not found in folder {self._gdrive_folder_id}")
                return None

            # Use the first matching file
            file_id = files[0]["id"]
            file_mime_type = files[0].get("mimeType", "")
            logger.debug(f"Found file '{filename}': {file_id} ({file_mime_type})")

            # Download the file content
            # For Google Docs/Sheets/Slides, use export_media
            # For regular files, use get_media
            if file_mime_type.startswith("application/vnd.google-apps."):
                # Google Workspace file - need to export
                # Determine export MIME type based on file type
                if "document" in file_mime_type:
                    export_mime = "text/plain"
                elif "spreadsheet" in file_mime_type:
                    export_mime = "text/csv"
                else:
                    export_mime = "text/plain"

                request = drive_service.files().export_media(fileId=file_id, mimeType=export_mime)
            else:
                # Regular file - download directly
                request = drive_service.files().get_media(fileId=file_id)

            # Download file content
            import io

            from googleapiclient.http import MediaIoBaseDownload

            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False

            while not done:
                status, done = downloader.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    logger.debug(f"Download progress for {filename}: {progress}%")

            # Get content as string
            content = fh.getvalue().decode("utf-8")
            logger.info(f"Successfully fetched file '{file_path}' from Google Drive ({len(content)} characters)")

            return content

        except Exception as e:
            logger.error(f"Error fetching file from Google Drive: {file_path}: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return None
