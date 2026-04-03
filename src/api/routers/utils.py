from functools import wraps

from fastapi import HTTPException
from fastapi import status as code

from ...exceptions.errors import (
    BadRequestError,
    UnauthorizedError,
    ForbiddenError,
    NotFoundError,
    ConflictError,
    ServiceError,
)
from ...utils.logger import logger



def handle_errors(func):
    @wraps(func)
    def endpoint_wrapper(*args, **kwargs):
        operation = func.__name__.replace("_", " ")
        try:
            return func(*args, **kwargs)
        except UnauthorizedError as e:
            logger.warning(f"API: unauthorized ({operation}): {e}")
            raise HTTPException(
                status_code=code.HTTP_401_UNAUTHORIZED,
                detail=str(e) or "Unauthorized",
            )
        except ForbiddenError as e:
            logger.warning(f"API: forbidden ({operation}): {e}")
            raise HTTPException(
                status_code=code.HTTP_403_FORBIDDEN,
                detail=str(e) or "Forbidden",
            )
        except NotFoundError as e:
            logger.info(f"API: not found ({operation}): {e}")
            raise HTTPException(
                status_code=code.HTTP_404_NOT_FOUND,
                detail=str(e) or "Not found",
            )
        except ConflictError as e:
            logger.info(f"API: conflict ({operation}): {e}")
            raise HTTPException(
                status_code=code.HTTP_409_CONFLICT,
                detail=str(e) or "Conflict",
            )
        except BadRequestError as e:
            logger.info(f"API: bad request ({operation}): {e}")
            raise HTTPException(
                status_code=code.HTTP_400_BAD_REQUEST,
                detail=str(e) or "Bad request",
            )
        except ServiceError as e:
            logger.error(f"API: service error ({operation}): {e}")
            raise HTTPException(
                status_code=code.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            )
        except HTTPException as e:
            if e.status_code == code.HTTP_401_UNAUTHORIZED:
                logger.warning(f"API: unauthorized ({operation}): {e.detail}")
            elif e.status_code == code.HTTP_403_FORBIDDEN:
                logger.warning(f"API: forbidden ({operation}): {e.detail}")
            elif e.status_code == code.HTTP_404_NOT_FOUND:
                logger.info(f"API: not found ({operation}): {e.detail}")
            raise
        except Exception as e:
            logger.error(f"API: failed to perform {operation}: {e}")
            raise HTTPException(
                status_code=code.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    return endpoint_wrapper
