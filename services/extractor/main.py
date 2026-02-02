"""Extractor service - Claim extraction using local LLM."""
import os
import json
import time
import uuid
import structlog
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError
import ollama

from .models import Claim, ExtractionRequest, ExtractionResponse
from .prompts import build_extraction_prompt

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()

app = FastAPI(
    title="Prompt Analyzer - Extractor Service",
    description="Semantic claim extraction from instructions",
    version="0.1.0",
)

# Ollama configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
MODEL = os.getenv("MODEL", "llama3.1:8b")

# Initialize Ollama client
try:
    ollama_client = ollama.Client(host=OLLAMA_HOST)
    logger.info("ollama_client_initialized", host=OLLAMA_HOST, model=MODEL)
except Exception as e:
    logger.error("ollama_client_init_failed", error=str(e))
    ollama_client = None


def generate_claim_id() -> str:
    """Generate unique claim ID."""
    return f"clm_{uuid.uuid4().hex[:12]}"


def extract_claims_from_text(event_id: str, session_id: str, text: str) -> list[Claim]:
    """Extract claims from instruction text using LLM."""
    if not ollama_client:
        logger.error("ollama_client_not_available")
        return []

    prompt = build_extraction_prompt(text)

    try:
        start_time = time.time()

        response = ollama_client.generate(
            model=MODEL,
            prompt=prompt,
            format="json",
            options={"temperature": 0.0}
        )

        duration_ms = (time.time() - start_time) * 1000

        logger.debug(
            "llm_response_received",
            event_id=event_id,
            duration_ms=duration_ms,
            response_length=len(response['response'])
        )

        # Parse LLM output
        try:
            raw_claims = json.loads(response['response'])

            # Handle case where LLM returns object instead of array
            if isinstance(raw_claims, dict):
                raw_claims = [raw_claims]

            if not isinstance(raw_claims, list):
                logger.warning("invalid_llm_output_type", type=type(raw_claims).__name__)
                return []

        except json.JSONDecodeError as e:
            logger.error("llm_output_parse_failed", error=str(e), output=response['response'][:200])
            return []

        # Validate with Pydantic
        validated_claims = []
        for i, raw in enumerate(raw_claims):
            try:
                claim = Claim(
                    claim_id=generate_claim_id(),
                    session_id=session_id,
                    event_id=event_id,
                    **raw
                )
                validated_claims.append(claim)
            except ValidationError as e:
                logger.warning(
                    "invalid_claim",
                    claim_index=i,
                    error=str(e),
                    raw_claim=raw
                )
                continue

        logger.info(
            "claims_extracted",
            event_id=event_id,
            claim_count=len(validated_claims),
            duration_ms=duration_ms
        )

        return validated_claims

    except Exception as e:
        logger.error("extraction_failed", event_id=event_id, error=str(e))
        return []


@app.post("/extract", response_model=ExtractionResponse)
async def extract_claims(request: ExtractionRequest):
    """Extract semantic claims from instruction text."""
    try:
        start_time = time.time()

        claims = extract_claims_from_text(
            event_id=request.event_id,
            session_id=request.session_id,
            text=request.text
        )

        extraction_time_ms = (time.time() - start_time) * 1000

        return ExtractionResponse(
            event_id=request.event_id,
            claims=claims,
            extraction_time_ms=extraction_time_ms
        )

    except Exception as e:
        logger.error("extract_endpoint_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/extract/batch", response_model=list[ExtractionResponse])
async def extract_batch(requests: list[ExtractionRequest]):
    """Extract claims from multiple events."""
    try:
        results = []
        for request in requests:
            start_time = time.time()

            claims = extract_claims_from_text(
                event_id=request.event_id,
                session_id=request.session_id,
                text=request.text
            )

            extraction_time_ms = (time.time() - start_time) * 1000

            results.append(ExtractionResponse(
                event_id=request.event_id,
                claims=claims,
                extraction_time_ms=extraction_time_ms
            ))

        return results

    except Exception as e:
        logger.error("batch_extract_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    """Health check endpoint."""
    try:
        if not ollama_client:
            raise Exception("Ollama client not initialized")

        # Test connection to Ollama
        try:
            ollama_client.list()
            ollama_status = "connected"
        except Exception as e:
            logger.error("ollama_health_check_failed", error=str(e))
            ollama_status = f"error: {str(e)}"

        return {
            "status": "healthy",
            "service": "extractor",
            "ollama_host": OLLAMA_HOST,
            "model": MODEL,
            "ollama_status": ollama_status
        }

    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
