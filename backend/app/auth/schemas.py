from dataclasses import dataclass


@dataclass
class CurrentUser:
    """从 Keycloak JWT claims 解析的用户信息。

    user_id 是 sub claim，作为业务系统用户唯一主键。
    roles 来自 resource_access.shouhou-gongdan-api.roles。
    """
    user_id: str
    username: str
    display_name: str
    email: str
    department_code: str
    department_name: str
    roles: list[str]
