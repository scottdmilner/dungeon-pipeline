from typing import Any, Optional

Incomplete = Any

NO_SSL_VALIDATION: bool
__version__: str


class ShotgunError(Exception): ...


class ShotgunFileDownloadError(ShotgunError): ...


class ShotgunThumbnailNotReady(ShotgunError): ...


class Fault(ShotgunError): ...


class AuthenticationFault(Fault): ...


class MissingTwoFactorAuthenticationFault(Fault): ...


class UserCredentialsNotAllowedForSSOAuthenticationFault(Fault): ...


class UserCredentialsNotAllowedForOxygenAuthenticationFault(Fault): ...


class ServerCapabilities:
    host: str
    server_info: dict
    version: tuple[int]
    is_dev: bool

    def __init__(self, host, meta) -> None: ...
    def ensure_include_archived_projects(self) -> None: ...
    def ensure_per_project_customization(self): ...
    def ensure_support_for_additional_filter_presets(self): ...
    def ensure_user_following_support(self): ...
    def ensure_paging_info_without_counts_support(self): ...
    def ensure_return_image_urls_support(self): ...


class ClientCapabilities:
    platform: str
    local_path_field: str
    py_version: str
    ssl_version: str

    def __init__(self) -> None: ...


class _Config:
    max_rpc_attempts: int
    rpc_attempt_interval: int
    timeout_secs: int
    api_ver: str
    convert_datetimes_to_utc: bool
    api_key: str
    script_name: str
    user_login: str
    user_password: str
    auth_token: str
    sudo_as_login: str
    extra_auth_params: dict
    session_uuid: str
    scheme: str
    server: str
    api_path: str
    raw_http_proxy: str
    proxy_handler: str
    proxy_server: str
    proxy_port: int
    proxy_user: str
    proxy_pass: str
    session_token: str
    authorization: str
    no_ssl_validation: bool
    localized: bool

    def __init__(self, sg) -> None: ...
    def set_server_params(self, base_url) -> None: ...
    @property
    def records_per_page(self): ...


class Shotgun:
    config: _Config
    base_url: str
    client_caps: ClientCapabilities

    def __init__(
        self,
        base_url: str,
        script_name: Optional[str] = None,
        api_key: Optional[str] = None,
        convert_datetimes_to_utc: bool = True,
        http_proxy: Optional[str] = None,
        ensure_ascii: bool = True,
        connect: Optional[bool] = True,
        ca_certs: Optional[str] = None,
        login: Optional[str] = None,
        password: Optional[str] = None,
        sudo_as_login: Optional[str] = None,
        session_token: Optional[str] = None,
        auth_token: Optional[str] = None,
    ) -> None: ...
    @property
    def server_info(self) -> dict: ...
    @property
    def server_caps(self) -> ServerCapabilities: ...
    def connect(self) -> None: ...
    def close(self) -> None: ...
    def info(self) -> dict: ...
    def find_one(
        self,
        entity_type: str,
        filters: list,
        fields: Optional[list] = None,
        order: Optional[int] = None,
        filter_operator: Optional[str] = None,
        retired_only: bool = False,
        include_archived_projects: bool = True,
        additional_filter_presets: Optional[list] = None,
    ) -> dict: ...
    def find(
        self,
        entity_type: str,
        filters: list,
        fields: Optional[list] = None,
        order: Optional[int] = None,
        filter_operator: Optional[str] = None,
        limit: int = 0,
        retired_only: bool = False,
        page: int = 0,
        include_archived_projects: bool = True,
        additional_filter_presets: Optional[list] = None,
    ) -> list: ...
    def summarize(
        self,
        entity_type: str,
        filters: list,
        summary_fields: list,
        filter_operator: Optional[str] = None,
        grouping: Optional[list] = None,
        include_archived_projects: bool = True,
    ): ...
    def create(
        self, entity_type: str, data: dict, return_fields: Optional[list[str]] = None
    ) -> dict: ...
    def update(
        self,
        entity_type: str,
        entity_id: int,
        data: dict,
        multi_entity_update_modes: Optional[dict] = None,
    ) -> dict: ...
    def delete(self, entity_type: str, entity_id: int) -> bool: ...
    def revive(self, entity_type: str, entity_id: int) -> bool: ...
    def batch(self, requests: list[dict]) -> list: ...
    def work_schedule_read(
        self,
        start_date,
        end_date,
        project: Optional[Incomplete] = None,
        user: Optional[Incomplete] = None,
    ): ...
    def work_schedule_update(
        self,
        date,
        working,
        description: Optional[Incomplete] = None,
        project: Optional[Incomplete] = None,
        user: Optional[Incomplete] = None,
        recalculate_field: Optional[Incomplete] = None,
    ): ...
    def follow(self, user, entity): ...
    def unfollow(self, user, entity): ...
    def followers(self, entity): ...
    def following(
        self,
        user,
        project: Optional[Incomplete] = None,
        entity_type: Optional[Incomplete] = None,
    ): ...
    def schema_entity_read(self, project_entity: Optional[Incomplete] = None): ...
    def schema_read(self, project_entity: Optional[Incomplete] = None): ...
    def schema_field_read(
        self,
        entity_type,
        field_name: Optional[Incomplete] = None,
        project_entity: Optional[Incomplete] = None,
    ): ...
    def schema_field_create(
        self,
        entity_type,
        data_type,
        display_name,
        properties: Optional[Incomplete] = None,
    ): ...
    def schema_field_update(
        self,
        entity_type,
        field_name,
        properties,
        project_entity: Optional[Incomplete] = None,
    ): ...
    def schema_field_delete(self, entity_type, field_name): ...
    def add_user_agent(self, agent) -> None: ...
    def reset_user_agent(self) -> None: ...
    def set_session_uuid(self, session_uuid) -> None: ...
    def share_thumbnail(
        self,
        entities,
        thumbnail_path: Optional[Incomplete] = None,
        source_entity: Optional[Incomplete] = None,
        filmstrip_thumbnail: bool = False,
        **kwargs,
    ): ...
    def upload_thumbnail(self, entity_type, entity_id, path, **kwargs): ...
    def upload_filmstrip_thumbnail(self, entity_type, entity_id, path, **kwargs): ...
    def upload(
        self,
        entity_type,
        entity_id,
        path,
        field_name: Optional[Incomplete] = None,
        display_name: Optional[Incomplete] = None,
        tag_list: Optional[Incomplete] = None,
    ): ...
    def download_attachment(
        self,
        attachment: bool = False,
        file_path: Optional[Incomplete] = None,
        attachment_id: Optional[Incomplete] = None,
    ): ...
    def set_up_auth_cookie(self) -> None: ...
    def get_attachment_download_url(self, attachment): ...
    def authenticate_human_user(
        self, user_login, user_password, auth_token: Optional[Incomplete] = None
    ): ...
    def update_project_last_accessed(
        self, project, user: Optional[Incomplete] = None
    ) -> None: ...
    def note_thread_read(self, note_id, entity_fields: Optional[Incomplete] = None): ...
    def text_search(
        self,
        text,
        entity_types,
        project_ids: Optional[Incomplete] = None,
        limit: Optional[Incomplete] = None,
    ): ...
    def activity_stream_read(
        self,
        entity_type,
        entity_id,
        entity_fields: Optional[Incomplete] = None,
        min_id: Optional[Incomplete] = None,
        max_id: Optional[Incomplete] = None,
        limit: Optional[Incomplete] = None,
    ): ...
    def nav_expand(
        self,
        path,
        seed_entity_field: Optional[Incomplete] = None,
        entity_fields: Optional[Incomplete] = None,
    ): ...
    def nav_search_string(
        self, root_path, search_string, seed_entity_field: Optional[Incomplete] = None
    ): ...
    def nav_search_entity(
        self, root_path, entity, seed_entity_field: Optional[Incomplete] = None
    ): ...
    def get_session_token(self): ...
    def preferences_read(self, prefs: Optional[Incomplete] = None): ...
    def schema(self, entity_type) -> None: ...
    def entity_types(self) -> None: ...
