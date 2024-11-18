from fastapi import FastAPI, HTTPException
from starlette import status
from pydantic import BaseModel, Field
import logging

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


@app.post(
    "/test_end_point",
    status_code=status.HTTP_201_CREATED,
)
def test_end_point(firstRequest: FirstRequestModel):
    try:
        # Error를 강제로 발생시켜 상황을 만듦
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The thread has not been created due to Internal Server Error"
        )
    except HTTPException as e:
        # 에러를 로깅
        logger.error(f"Error occurred: Status Code: {e.status_code}, Detail: {e.detail}")
        # FastAPI가 에러를 렌더링할 수 있도록 다시 발생
        raise e


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
