import os
import google.generativeai as genai


class GeminiClient:
    """
    Google Gemini AI 모델을 관리하고 호출하는 중앙 클라이언트 클래스입니다.
    싱글턴(Singleton) 패턴을 적용하여, 앱 전체에서 단 하나의 인스턴스만 사용하도록 합니다.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            print("INFO:     Initializing Gemini AI Client...")
            cls._instance = super(GeminiClient, cls).__new__(cls)
            cls._instance._configure()
        return cls._instance

    def _configure(self):
        """API 키를 설정하고, 사용 가능한 모델들을 초기화합니다."""
        try:
            GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
            if not GOOGLE_API_KEY:
                raise ValueError("GOOGLE_API_KEY is not set in environment variables.")
            genai.configure(api_key=GOOGLE_API_KEY)

            # 사용할 모델들을 속성으로 등록합니다.
            self.flash_model = genai.GenerativeModel('gemini-1.5-flash-latest')
            self.pro_model = genai.GenerativeModel('gemini-1.5-pro-latest')
            print("INFO:     Gemini AI Client initialized successfully.")

        except Exception as e:
            raise RuntimeError(f"Failed to configure Gemini AI Client: {e}")

    async def generate_text(self, prompt: str, pro_model: bool = False) -> str:
        """
        주어진 프롬프트로부터 텍스트를 생성합니다.
        :param prompt: AI에게 보낼 프롬프트
        :param pro_model: True일 경우 Pro 모델을, False일 경우 Flash 모델(기본값)을 사용합니다.
        :return: 생성된 텍스트
        """
        model = self.pro_model if pro_model else self.flash_model

        try:
            response = await model.generate_content_async(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"Error during Gemini text generation: {e}")
            # 에러 발생 시, 빈 문자열이나 특정 에러 메시지를 반환할 수 있습니다.
            return ""


# --- 싱글턴 인스턴스 생성 ---
# 다른 파일에서는 이 'gemini_client'를 임포트하여 사용합니다.
gemini_client = GeminiClient()