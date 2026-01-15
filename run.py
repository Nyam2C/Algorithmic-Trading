#!/usr/bin/env python3
"""
High-Win Survival System - 통합 실행 스크립트 (Python 버전)
Sprint 1: Paper Trading MVP

Windows/Linux/Mac 모두에서 사용 가능한 Python 스크립트
"""
import os
import sys
import subprocess
from pathlib import Path

# 색상 코드 (Windows에서도 작동)
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    GREEN = Fore.GREEN
    RED = Fore.RED
    YELLOW = Fore.YELLOW
    BLUE = Fore.BLUE
    RESET = Style.RESET_ALL
except ImportError:
    # colorama가 없으면 색상 없이 출력
    GREEN = RED = YELLOW = BLUE = RESET = ""


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
    print("   High-Win Survival System - Sprint 1 MVP")
    print("   Binance Testnet + Gemini AI Trading Bot")
    print("=" * 60 + "\n")


def check_python():
    """Python 버전 체크"""
    log_info("Python 버전 확인 중...")
    version = sys.version.split()[0]
    major, minor = map(int, version.split(".")[:2])

    if major < 3 or (major == 3 and minor < 8):
        log_error(f"Python 3.8 이상이 필요합니다. (현재: {version})")
        sys.exit(1)

    log_success(f"Python 버전: {version}")


def install_dependencies(skip=False):
    """의존성 패키지 설치"""
    if skip:
        log_info("의존성 설치 건너뜀 (--skip-install)")
        return

    log_info("의존성 패키지 설치 중...")

    requirements_file = Path("requirements.txt")
    if not requirements_file.exists():
        log_error("requirements.txt 파일이 없습니다.")
        sys.exit(1)

    try:
        # pip 업그레이드
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "pip", "-q"],
            check=True,
        )

        # 의존성 설치
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"],
            check=True,
        )

        log_success("의존성 설치 완료")
    except subprocess.CalledProcessError as e:
        log_error(f"의존성 설치 실패: {e}")
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

        # .env.example 복사
        with open(env_example, "r", encoding="utf-8") as f:
            content = f.read()

        with open(env_file, "w", encoding="utf-8") as f:
            f.write(content)

        log_warning(".env 파일을 생성했습니다. API 키를 입력해주세요!")
        print("\n필수 설정 항목:")
        print("  - BINANCE_API_KEY (Binance Testnet API 키)")
        print("  - BINANCE_SECRET_KEY (Binance Testnet Secret 키)")
        print("  - GEMINI_API_KEY (Gemini AI API 키)")
        print("  - DISCORD_WEBHOOK_URL (Discord Webhook URL)")
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

    # Binance API Key
    binance_key = os.getenv("BINANCE_API_KEY", "")
    if not binance_key or binance_key == "your_binance_testnet_api_key":
        missing_keys.append("BINANCE_API_KEY")

    # Binance Secret Key
    binance_secret = os.getenv("BINANCE_SECRET_KEY", "")
    if not binance_secret or binance_secret == "your_binance_testnet_secret_key":
        missing_keys.append("BINANCE_SECRET_KEY")

    # Gemini API Key
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if not gemini_key or gemini_key == "your_gemini_api_key":
        missing_keys.append("GEMINI_API_KEY")

    # Discord Webhook
    discord_webhook = os.getenv("DISCORD_WEBHOOK_URL", "")
    if not discord_webhook or "your-webhook-url" in discord_webhook:
        missing_keys.append("DISCORD_WEBHOOK_URL")

    if missing_keys:
        log_error("다음 API 키가 설정되지 않았습니다:")
        for key in missing_keys:
            print(f"  - {key}")
        print("\nAPI 키 발급 방법:")
        print("  1. Binance Testnet: https://testnet.binancefuture.com")
        print("  2. Gemini AI: https://aistudio.google.com/apikey")
        print("  3. Discord Webhook: Discord 서버 설정 > 연동 > 웹후크")
        print()
        sys.exit(1)

    log_success("API 키 검증 완료")


def test_imports():
    """모듈 Import 테스트"""
    log_info("모듈 Import 테스트 중...")

    modules = [
        ("src.config", "get_config"),
        ("src.exchange.binance", "BinanceTestnetClient"),
        ("src.data.indicators", "analyze_market"),
        ("src.ai.gemini", "GeminiSignalGenerator"),
        ("src.trading.executor", "TradingExecutor"),
    ]

    for module_name, class_name in modules:
        try:
            module = __import__(module_name, fromlist=[class_name])
            getattr(module, class_name)
            log_success(f"✓ {module_name}")
        except Exception as e:
            log_error(f"✗ {module_name} - Import 실패: {e}")
            sys.exit(1)

    log_success("모든 모듈 Import 성공")


def run_bot():
    """봇 실행"""
    log_info("트레이딩 봇 시작...")
    print("\n" + "=" * 60)
    print("  봇이 실행됩니다. Ctrl+C로 중지할 수 있습니다.")
    print("=" * 60 + "\n")

    try:
        # main.py 실행
        subprocess.run([sys.executable, "-m", "src.main"], check=True)
    except KeyboardInterrupt:
        print("\n\n봇이 중지되었습니다.")
    except subprocess.CalledProcessError as e:
        log_error(f"봇 실행 중 오류 발생: {e}")
        sys.exit(1)


def main():
    """메인 실행"""
    # 프로젝트 루트로 이동
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    # 배너 출력
    print_banner()

    # --skip-install 옵션 체크
    skip_install = "--skip-install" in sys.argv

    # 1. Python 체크
    check_python()

    # 2. 의존성 설치
    install_dependencies(skip=skip_install)

    # 3. .env 파일 체크
    check_env_file()

    # 4. API 키 검증
    validate_api_keys()

    # 5. Import 테스트
    test_imports()

    print()
    log_success("모든 사전 체크 완료! 봇을 시작합니다...")
    print()

    import time
    time.sleep(2)

    # 6. 봇 실행
    run_bot()


if __name__ == "__main__":
    main()
