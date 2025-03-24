from typing import Any, Dict, Type, Union, List, Optional
from pydantic import BaseModel, create_model, Field
from openai import OpenAI
import inspect
import google.generativeai as genai
import instructor
import os

# A small helper map from string -> Python type
BUILTIN_TYPES: Dict[str, Any] = {
    "int": int,
    "str": str,
    "List[str]": List[str],
    "bool": bool,
}

provider_model_map = {
    "google": "gemini-2.0-flash-exp",
    "ollama": "llama3.2:latest",
    "groq": "llama3.2:latest",
}



class FastClass:
    """
    A convenience class that wraps Google Generative AI with 'instructor' in JSON mode.
    It can accept either a string-based type definition or a full Pydantic model.
    """

    def __init__(self, provider: str = "Google", model_name: str = "models/gemini-2.0-flash-exp", llm_api_key: str = None):
        # Initialize LLM client
        self.provider = provider.lower()
        self.model_name = model_name
        if self.provider == "google":
            llm_api_key = llm_api_key or os.environ.get("GOOGLE_API_KEY")
            if not llm_api_key:
                raise ValueError("Google API key is required")
            genai.configure(api_key=llm_api_key)
            self.client = instructor.from_gemini(
                client=genai.GenerativeModel(model_name=self.model_name),
                mode=instructor.Mode.GEMINI_JSON,
            )
        elif self.provider == "ollama":
            self.client = instructor.from_openai(
                OpenAI(
                    base_url={
                        "container": "http://ollama:11434/v1",
                        "local": "http://localhost:11434/v1"
                    }.get(os.environ.get("OPOL_MODE", ""), None),
                    api_key='ollama',
                ),
                mode=instructor.Mode.JSON,
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    # Central available providers
    @staticmethod
    def available_providers():
        return list(provider_model_map.keys())

    def infer(
        self,
        type_or_model: Union[str, Type[BaseModel]],
        user_input: str,
        prompt: Optional[str] = None,
    ) -> Any:
        """
        Dynamically infer the result from the LLM.

        :param type_or_model: Either a string indicating a builtin type
                              or a Pydantic model class.
        :param prompt: The high-level instructions for the LLM.
        :param user_input: The user-provided text or context to classify.
        :return: Either a basic Python type (int, str, list[str], bool) or a
                 Pydantic model instance, depending on what was requested.
        """
        # 1) Build the prompt
        combined_prompt = self._build_prompt(type_or_model, prompt, user_input)

        # 2) Create the appropriate "response_model" for the instructor client.
        if isinstance(type_or_model, str):
            # string-based type => create single-field dynamic model
            dynamic_model = self._create_single_field_model(type_or_model)
            response_model = dynamic_model
        else:
            # type_or_model is a Pydantic class
            response_model = type_or_model

        # 3) Call the LLM and parse JSON → Pydantic
        if self.provider == "google":
            llm_response = self.client.messages.create(
                messages=[
                    {"role": "user", "content": combined_prompt}
                ],
                response_model=response_model,
            )
        elif self.provider == "ollama":
            llm_response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": combined_prompt}
                ],
                response_model=response_model,
            )
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

        # 4) If it was a single-field dynamic model, extract that field value. Otherwise return model instance.
        if isinstance(type_or_model, str):
            field_name = list(llm_response.model_fields.keys())[0]
            return getattr(llm_response, field_name)
        else:
            return llm_response

    def _build_prompt(
        self,
        type_or_model: Union[str, Type[BaseModel]],
        prompt: Optional[str],
        user_input: str
    ) -> str:
        """
        Build a textual prompt with the hierarchy:
          1) 'prompt' argument
          2) Model docstring (if a BaseModel)
          3) Field descriptions (if a BaseModel)
          4) The user's input text
        """
        lines = []
        if prompt:
            lines.append(prompt.strip())

        # If we have a Pydantic model, incorporate docstring + field descriptions.
        if not isinstance(type_or_model, str):
            model_doc = inspect.getdoc(type_or_model) or ""
            if model_doc:
                lines.append(f"\nMODEL DESCRIPTION:\n{model_doc}")

            # For each field, add its description if present.
            for field_name, field_def in type_or_model.model_fields.items():
                if field_def.description:
                    lines.append(
                        f"\nFIELD '{field_name}' DESCRIPTION: {field_def.description}"
                    )

        # Finally, the user input
        lines.append(f"\nUSER INPUT:\n{user_input}")

        return "\n".join(lines).strip()

    def _create_single_field_model(self, type_str: str) -> Type[BaseModel]:
        """
        Dynamically create a single-field Pydantic model from a string type
        e.g. "int", "List[str]", "bool", ...
        """
        if type_str not in BUILTIN_TYPES:
            raise ValueError(
                f"Type '{type_str}' not recognized. "
                f"Please add it to BUILTIN_TYPES if you need it."
            )

        field_type = BUILTIN_TYPES[type_str]
        dynamic_model = create_model(
            "DynamicSingleFieldModel",
            __base__=BaseModel,
            single_field=(field_type, Field(..., description=f"A {type_str} value.")),
        )
        return dynamic_model