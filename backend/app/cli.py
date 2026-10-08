import argparse
import getpass
import sys

from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import BusinessError
from app.repositories.database import create_database_engine, create_session_factory
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.identity import AccountInput
from app.services.auth import AuthService


def main() -> None:
    parser = argparse.ArgumentParser(description="SoloOps 本机账号管理")
    parser.add_argument("action", choices=["create-user", "reset-password"])
    parser.add_argument("username")
    parser.add_argument("--password-stdin", action="store_true", help="从标准输入读取密码")
    args = parser.parse_args()
    password = (
        sys.stdin.readline().rstrip("\r\n") if args.password_stdin else getpass.getpass("密码: ")
    )
    try:
        data = AccountInput(username=args.username.strip().lower(), password=password)
    except ValidationError:
        parser.error("账号需为 3–64 个小写字母、数字或 ._-；密码长度需为 12–128")
    settings = Settings()
    engine = create_database_engine(settings)
    try:
        with create_session_factory(engine)() as session:
            service = AuthService(UnitOfWork(session), settings)
            if args.action == "create-user":
                service.create_account(data)
            else:
                service.reset_password(data)
    except BusinessError as error:
        parser.error(error.message)
    finally:
        engine.dispose()
    print("账号已创建。" if args.action == "create-user" else "密码已更新，原会话均已撤销。")


if __name__ == "__main__":
    main()
