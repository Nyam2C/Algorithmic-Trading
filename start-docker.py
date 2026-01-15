#!/usr/bin/env python3
"""
High-Win Survival System - Docker 통합 실행 스크립트 (Python)
Docker 빌드 → 컨테이너 실행 → 봇 동작을 한 번에 처리
Windows/Linux/Mac 모두 지원
"""
import os
import sys
import subprocess
import time
from pathlib import Path

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    GREEN = Fore.GREEN
    RED = Fore.RED
    YELLOW = Fore.YELLOW
    BLUE = Fore.BLUE
    CYAN = Fore.CYAN
    RESET = Style.RESET_ALL
except ImportError:
    GREEN = RED = YELLOW = BLUE = CYAN = RESET = ""


def log_info(msg):
    print(f"{BLUE}[INFO]{RESET} {msg}")


def log_success(msg):
    print(f"{GREEN}[SUCCESS]{RESET} {msg}")


def log_warning(msg):
    print(f"{YELLOW}[WARNING]{RESET} {msg}")


def log_error(msg):
    print(f"{RED}[ERROR]{RESET} {msg}")


def print_banner():
    print("\n" + "=" * 60)
    print("   High-Win Survival System - Docker Deployment")
    print("   One-Click Build & Run with Docker")
    print("=" * 60 + "\n")


def check_docker():
    """Docker 설치 확인"""
    log_info("Docker 설치 확인 중...")

    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        version = result.stdout.strip()
        log_success(f"Docker: {version}")

        # Docker daemon 실행 확인
        subprocess.run(
            ["docker", "info"],
            capture_output=True,
            check=True
        )
        log_success("Docker daemon 실행 중")

    except FileNotFoundError:
        log_error("Docker가 설치되어 있지 않습니다.")
        print("\nDocker 설치:")
        print("  Windows: https://docs.docker.com/desktop/install/windows-install/")
        print("  Mac: https://docs.docker.com/desktop/install/mac-install/")
        print("  Linux: https://docs.docker.com/engine/install/")
        sys.exit(1)

    except subprocess.CalledProcessError:
        log_error("Docker가 실행되고 있지 않습니다.")
        print("Docker Desktop을 시작해주세요.")
        sys.exit(1)


def check_docker_compose():
    """Docker Compose 확인"""
    log_info("Docker Compose 확인 중...")

    # docker compose (v2) 먼저 확인
    try:
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            text=True,
            check=True
        )
        compose_cmd = ["docker", "compose"]
        version = result.stdout.strip()
        log_success(f"Docker Compose: {version}")
        return compose_cmd

    except subprocess.CalledProcessError:
        # docker-compose (v1) 확인
        try:
            result = subprocess.run(
                ["docker-compose", "--version"],
                capture_output=True,
                text=True,
                check=True
            )
            compose_cmd = ["docker-compose"]
            version = result.stdout.strip()
            log_success(f"Docker Compose: {version}")
            return compose_cmd

        except (FileNotFoundError, subprocess.CalledProcessError):
            log_error("Docker Compose가 설치되어 있지 않습니다.")
            sys.exit(1)


def check_env_file():
    """환경 변수 파일 체크"""
    log_info(".env 파일 확인 중...")

    env_file = Path(".env")
    env_example = Path(".env.example")

    if not env_file.exists():
        log_warning(".env 파일이 없습니다. .env.example을 복사합니다...")

        if not env_example.exists():
            log_error(".env.example 파일도 없습니다.")
            sys.exit(1)

        with open(env_example, "r", encoding="utf-8") as f:
            content = f.read()

        with open(env_file, "w", encoding="utf-8") as f:
            f.write(content)

        log_warning(".env 파일을 생성했습니다.")
        print("\n⚠️  필수: .env 파일에 API 키를 입력해주세요!\n")
        print("필수 항목:")
        print("  - BINANCE_API_KEY")
        print("  - BINANCE_SECRET_KEY")
        print("  - GEMINI_API_KEY")
        print("  - DISCORD_WEBHOOK_URL")
        print()
        input(".env 파일 편집을 완료했으면 Enter를 눌러주세요...")
    else:
        log_success(".env 파일 존재")


def validate_api_keys():
    """API 키 검증"""
    log_info("API 키 검증 중...")

    from dotenv import load_dotenv
    load_dotenv()

    missing_keys = []

    binance_key = os.getenv("BINANCE_API_KEY", "")
    if not binance_key or binance_key == "your_binance_testnet_api_key":
        missing_keys.append("BINANCE_API_KEY")

    binance_secret = os.getenv("BINANCE_SECRET_KEY", "")
    if not binance_secret or binance_secret == "your_binance_testnet_secret_key":
        missing_keys.append("BINANCE_SECRET_KEY")

    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if not gemini_key or gemini_key == "your_gemini_api_key":
        missing_keys.append("GEMINI_API_KEY")

    discord_webhook = os.getenv("DISCORD_WEBHOOK_URL", "")
    if not discord_webhook or "your-webhook-url" in discord_webhook:
        missing_keys.append("DISCORD_WEBHOOK_URL")

    if missing_keys:
        log_error("다음 API 키가 설정되지 않았습니다:")
        for key in missing_keys:
            print(f"  - {key}")
        print("\nAPI 키 발급:")
        print("  1. Binance Testnet: https://testnet.binancefuture.com")
        print("  2. Gemini AI: https://aistudio.google.com/apikey")
        print("  3. Discord Webhook: Discord 서버 > 설정 > 연동 > 웹후크")
        sys.exit(1)

    log_success("API 키 검증 완료")


def stop_existing_containers(compose_cmd):
    """기존 컨테이너 정리"""
    log_info("기존 컨테이너 정리 중...")

    try:
        result = subprocess.run(
            compose_cmd + ["ps"],
            capture_output=True,
            text=True
        )

        if "trading-bot" in result.stdout:
            log_warning("기존 컨테이너를 중지합니다...")
            subprocess.run(compose_cmd + ["down"], check=True)
            log_success("기존 컨테이너 중지 완료")
        else:
            log_info("실행 중인 컨테이너 없음")

    except subprocess.CalledProcessError as e:
        log_warning(f"컨테이너 정리 중 오류 (무시): {e}")


def build_docker_image(compose_cmd):
    """Docker 이미지 빌드"""
    log_info("Docker 이미지 빌드 중...")
    print()

    try:
        subprocess.run(
            compose_cmd + ["build", "--no-cache"],
            check=True
        )
        log_success("Docker 이미지 빌드 완료")

    except subprocess.CalledProcessError:
        log_error("Docker 이미지 빌드 실패")
        sys.exit(1)


def start_containers(compose_cmd):
    """컨테이너 시작"""
    log_info("Docker 컨테이너 시작 중...")
    print()

    try:
        # PostgreSQL 먼저 시작
        log_info("PostgreSQL 컨테이너 시작...")
        subprocess.run(
            compose_cmd + ["up", "-d", "postgres"],
            check=True
        )

        log_info("PostgreSQL 헬스체크 대기 중...")
        time.sleep(5)

        # Trading Bot 시작
        log_info("Trading Bot 컨테이너 시작...")
        subprocess.run(
            compose_cmd + ["up", "-d", "trading-bot"],
            check=True
        )

        log_success("컨테이너 시작 완료")

    except subprocess.CalledProcessError:
        log_error("컨테이너 시작 실패")
        sys.exit(1)


def show_status(compose_cmd):
    """컨테이너 상태 표시"""
    print()
    log_info("실행 중인 컨테이너:")
    print()

    try:
        subprocess.run(compose_cmd + ["ps"])
    except subprocess.CalledProcessError:
        log_warning("컨테이너 상태 확인 실패")

    print()


def show_logs(compose_cmd):
    """로그 표시"""
    print()
    log_success("봇이 실행되었습니다!")
    print()
    print("=" * 60)
    print("  로그 확인 방법:")
    print(f"    {' '.join(compose_cmd)} logs -f trading-bot")
    print()
    print("  컨테이너 중지:")
    print(f"    {' '.join(compose_cmd)} down")
    print()
    print("  컨테이너 재시작:")
    print(f"    {' '.join(compose_cmd)} restart trading-bot")
    print("=" * 60)
    print()

    choice = input("실시간 로그를 확인하시겠습니까? (y/N): ").strip().lower()
    if choice in ['y', 'yes']:
        print()
        log_info("로그 스트리밍 시작 (Ctrl+C로 종료)")
        print()
        try:
            subprocess.run(compose_cmd + ["logs", "-f", "trading-bot"])
        except KeyboardInterrupt:
            print("\n로그 스트리밍 종료")


def main():
    """메인 실행"""
    # 프로젝트 루트로 이동
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    print_banner()

    # 1. Docker 확인
    check_docker()
    compose_cmd = check_docker_compose()

    # 2. .env 파일 확인
    check_env_file()

    # 3. API 키 검증
    validate_api_keys()

    # 4. 기존 컨테이너 정리
    stop_existing_containers(compose_cmd)

    # 5. Docker 이미지 빌드
    build_docker_image(compose_cmd)

    # 6. 컨테이너 시작
    start_containers(compose_cmd)

    # 7. 상태 확인
    show_status(compose_cmd)

    # 8. 로그 표시
    show_logs(compose_cmd)


if __name__ == "__main__":
    main()
