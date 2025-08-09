# 2025-likelion-Team1-BE

## 개발 환경
- Python 3.9.23
- 패키지 관리자: pip
- 가상환경: venv 사용 (권장)

## 개발 환경 설정

1.  **저장소를 클론합니다.**
    ```bash
    git clone https://github.com/2025-LikeLion-Team1/2025-likelion-Team1-BE.git
    ```

2.  **가상 환경을 생성하고 활성화합니다.**
    ```bash
    python -m venv venv
    source venv/bin/activate
    ```

3.  **필요한 패키지를 설치합니다.**
    ```bash
    pip install -r requirements.txt
    ```

4.  **.env 파일을 설정합니다.**
    `.env.example` 파일을 복사하여 `.env` 파일을 생성한 후, 내부의 환경 변수들을 자신의 로컬 환경에 맞게 수정해주세요.
    ```bash
    cp .env.example .env
    ```