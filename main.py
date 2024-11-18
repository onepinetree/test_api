import logging
from fastapi import FastAPI, HTTPException
from starlette import status
import uvicorn
from pydantic import BaseModel, Field
from typing import Literal
import time


# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("fastapi-logger")


app = FastAPI()


class FirstRequestModel(BaseModel):
    first_prompt: str = Field(
        ..., 
        min_length=1,
        description='Input first_prompt'
    )

    model_config = {
        "json_schema_extra": {
            'example': {
                'first_prompt': '오늘 하루 어땠어?😀'
            }
        }
    }


@app.post(
    "/test_end_point",
    status_code=status.HTTP_201_CREATED,
)
def testEndPoint(firstRequest: FirstRequestModel):
    error_status = True

    if error_status:
        try:
            raise Exception("Simulated internal server error")
        except Exception as e:
            # 로그에 상세 정보 기록
            logger.error(f"Error occurred: The thread has not been created due to Internal Server Error, {e}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"The thread has not been created due to Internal Server Error, {e}"
            )
    else:
        return {"message": "Hello"}


# 애플리케이션 실행
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
