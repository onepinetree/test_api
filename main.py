import logging
from fastapi import FastAPI, HTTPException
from starlette import status
from pydantic import BaseModel, Field
import time
from openai import OpenAI
import os


# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("fastapi-logger")

# OpenAI 및 HTTP 라이브러리 로그 수준 조정
logging.getLogger("httpx").setLevel(logging.INFO)  # HTTP 요청/응답 정보는 INFO 수준으로 표시
logging.getLogger("httpcore").setLevel(logging.INFO)  # HTTP 코어 라이브러리 INFO 수준
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

API_KEY = os.getenv('API_KEY')
tori_assistant_id = os.getenv('tori_assistant_id')

client = OpenAI(api_key=API_KEY, project='proj_YA4wA5gFbCTSd8ImZ1UapNJN')

app = FastAPI()


class MessageModel(BaseModel):
    thread_id: str = Field(..., min_length=1, description="Input user's thread_id")
    new_user_message: str = Field(..., min_length=1, description="Input user prompt")

    model_config = {
        "json_schema_extra": {
            "example": {
                "thread_id": "thread_ysvw3IGw9WH2NgGtas8qvNdX",
                "new_user_message": "오늘은 좋은 하루였어",
            }
        }
    }


class ToriResponseModel(BaseModel):
    tori_message: str


def createMessageInThread(threadId: str, role: str, content: str):
    client.beta.threads.messages.create(thread_id=threadId, role=role, content=content)


def createRun(thread_id: str, assistant_id: str):
    return client.beta.threads.runs.create(thread_id=thread_id, assistant_id=assistant_id)


def retrieveRun(thread_id: str, run_id: str):
    return client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)


@app.post(
    "/retrieve_tori_message",
    status_code=status.HTTP_201_CREATED,
    response_model=ToriResponseModel,
    responses={
        404: {
            "description": "Failed to CreateMessageInThread",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to CreateMessageInThread, <Error Explanation>"
                    }
                }
            },
        },
        500: {
            "description": "Internal Server Error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to <Failed Job>, <Error Explanation>"
                    }
                }
            },
        },
    },
)
async def getMessageFromTori(model: MessageModel) -> ToriResponseModel:
    thread_id = model.thread_id
    user_prompt = model.new_user_message

    logger.info("Starting process to retrieve Tori message.")
    logger.debug(f"Thread ID: {thread_id}, User Prompt: {user_prompt}")

    try:
        createMessageInThread(
            threadId=thread_id,
            role="user",
            content=user_prompt,
        )
    except Exception as e:
        logger.error(f"Failed to CreateMessageInThread: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Failed to CreateMessageInThread, {e}",
        )

    try:
        run = createRun(thread_id=thread_id, assistant_id=tori_assistant_id)
        run_id = run.id
    except Exception as e:
        logger.error(f"Failed to CreateRun: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to CreateRun, {e}",
        )

    timeout = time.time() + 15  # 15 seconds timeout

    while True:
        try:
            retrieve_run = retrieveRun(thread_id=thread_id, run_id=run_id)
        except Exception as e:
            logger.error(f"Failed to RetrieveRun: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to RetrieveRun, {e}",
            )

        if retrieve_run.status == "completed":
            logger.info("Run completed successfully. Retrieving messages.")
            thread_messages = client.beta.threads.messages.list(thread_id)
            tori_message = thread_messages.data[0].content[0].text.value
            return ToriResponseModel(tori_message=tori_message)

        elif retrieve_run.status in ["queued", "in_progress"]:
            logger.debug("Run is in progress. Retrying...")
            time.sleep(0.5)
        else:
            logger.error(
                f"Failed to get completed status from Run and got {retrieve_run.status}, {Exception}"
            )
            return ToriResponseModel(
                tori_message="(토리가 잠깐 딴 생각을 했나봐요! 다시 한번 토리를 불러주세요 ㅜㅜ)"
            )

        if time.time() > timeout:
            logger.error("Timeout while waiting for the run to complete.")
            return ToriResponseModel(
                tori_message="(토리가 잠깐 딴 생각을 했나봐요! 다시 한번 토리를 불러주세요 ㅜㅜ)"
            )




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
