import logging
import os
from typing import List, Dict, Any

import ask_sdk_core.utils as ask_utils
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_model import Response
from openai import OpenAI

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

OPENAI_API_KEY = "<YOUR_OPENAI_API_KEY>"  # Substitua pela sua chave da OpenAI
OPENAI_MODEL = "<YOUR_OPENAI_MODEL>"  # Substitua pelo modelo desejado, ex: "gpt-5.2"
OPENAI_TEMPERATURE = "<YOUR_OPENAI_TEMPERATURE>"  # Substitua pela temperatura desejada, ex: "0.7"
OPENAI_MAX_TOKENS = "<YOUR_OPENAI_MAX_TOKENS>"  # Substitua pelo número máximo de tokens, ex: "150"
OPENAI_TIMEOUT = "<YOUR_OPENAI_TIMEOUT>"  # Substitua pelo timeout desejado em segundos, ex: "10"
MAX_HISTORY_TURNS = "<YOUR_MAX_HISTORY_TURNS>"  # Substitua pelo número máximo de turnos de histórico, ex: "5"

client = OpenAI(api_key=OPENAI_API_KEY, timeout=OPENAI_TIMEOUT)

SYSTEM_PROMPT = (
    "Você é uma assistente muito útil. Responda de forma clara e concisa em "
    "Português do Brasil. Use frases curtas, evite jargões e ofereça exemplos "
    "simples quando fizer sentido."
)


def _base_messages() -> List[Dict[str, str]]:
    return [{"role": "system", "content": SYSTEM_PROMPT}]


def _sanitize_speech(text: str) -> str:
    return " ".join(text.split())


def _get_session_messages(handler_input: HandlerInput) -> List[Dict[str, str]]:
    session = handler_input.attributes_manager.session_attributes
    messages = session.get("messages")
    if not messages:
        messages = _base_messages()
    return messages


def _store_session_messages(handler_input: HandlerInput, messages: List[Dict[str, str]]):
    session = handler_input.attributes_manager.session_attributes
    session["messages"] = messages


class LaunchRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool

        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        _store_session_messages(handler_input, _base_messages())
        speak_output = (
            "Aqui é o ChatGPT, estou à sua disposição."
        )

        return (
            handler_input.response_builder.speak(speak_output).ask(speak_output).response
        )


class GptQueryIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("GptQueryIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        slots = handler_input.request_envelope.request.intent.slots or {}
        query_slot = slots.get("query")
        query = query_slot.value if query_slot else None
        if not query:
            speak_output = "Não entendi a pergunta. Você pode repetir?"
            return (
                handler_input.response_builder.speak(speak_output)
                .ask(speak_output)
                .response
            )

        response = generate_gpt_response(handler_input, query)
        response = _sanitize_speech(response)

        return (
            handler_input.response_builder.speak(response)
            .ask("Você pode fazer outra pergunta ou dizer: sair.")
            .response
        )


def generate_gpt_response(handler_input: HandlerInput, query: str) -> str:
    try:
        if not OPENAI_API_KEY:
            return "A chave da OpenAI não está configurada. Ajuste a variável OPENAI_API_KEY."

        messages = _get_session_messages(handler_input)
        messages.append({"role": "user", "content": query})
        messages = messages[:1] + messages[-(MAX_HISTORY_TURNS * 2) :]
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_completion_tokens=OPENAI_MAX_TOKENS,
            temperature=OPENAI_TEMPERATURE,
        )
        reply = response.choices[0].message.content
        messages.append({"role": "assistant", "content": reply})
        _store_session_messages(handler_input, messages)
        return reply
    except Exception as e:
        logger.error("Erro ao gerar resposta", exc_info=True)
        return "Tive um problema para responder agora. Tente novamente em alguns segundos."


class HelpIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Diga sua pergunta, por exemplo: como funciona a fotossíntese."

        return (
            handler_input.response_builder.speak(speak_output).ask(speak_output).response
        )


class CancelOrStopIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.CancelIntent")(
            handler_input
        ) or ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Até logo!"

        return handler_input.response_builder.speak(speak_output).response


class SessionEndedRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response

        # Any cleanup logic goes here.

        return handler_input.response_builder.response


class FallbackIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Não entendi. Faça uma pergunta ou diga: ajuda."
        return (
            handler_input.response_builder.speak(speak_output).ask(speak_output).response
        )


class CatchAllExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> bool
        return True

    def handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> Response
        logger.error(exception, exc_info=True)

        speak_output = "Desculpe, não consegui processar sua solicitação."

        return (
            handler_input.response_builder.speak(speak_output)
            .ask(speak_output)
            .response
        )


sb = SkillBuilder()

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(GptQueryIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_request_handler(FallbackIntentHandler())

sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()
