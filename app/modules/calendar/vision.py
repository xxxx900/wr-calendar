from __future__ import annotations

import base64
import json
from typing import Any

from openai import AsyncOpenAI


class OpenAICalendarVision:
    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    @staticmethod
    def _prepare_image_urls(file_bytes: bytes) -> list[dict[str, Any]]:
        if file_bytes.startswith(b"%PDF-"):
            import io
            import pypdfium2 as pdfium

            try:
                pdf = pdfium.PdfDocument(file_bytes)
                image_urls = []
                for page in pdf:
                    pil_image = page.render(scale=2).to_pil()
                    buf = io.BytesIO()
                    pil_image.save(buf, format="JPEG", quality=90)
                    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
                    image_urls.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}})
                if not image_urls:
                    raise ValueError("PDF document contains no renderable pages.")
                return image_urls
            except Exception as exc:
                raise ValueError(f"Failed to process PDF document: {exc}") from exc
        else:
            encoded = base64.b64encode(file_bytes).decode("ascii")
            mime = "image/png" if file_bytes.startswith(b"\x89PNG") else "image/jpeg"
            return [{"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}}]

    async def __call__(self, image_bytes: bytes) -> list[dict[str, Any]]:
        image_content_parts = self._prepare_image_urls(image_bytes)
        user_content: list[dict[str, Any]] = [
            {"type": "text", "text": "Extract all visible events from this calendar image/document."}
        ] + image_content_parts

        response = await self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        """
                        You are an expert data extraction assistant. Your task is to extract community events from the provided calendar image/PDF and return a valid JSON array directly insertable into a PostgreSQL / Supabase table.
                        Extract community calendar events. Return JSON with an events array. 
                        Use ISO dates and UTC timestamps where times are present. 
                        Do not invent missing values.

                        ### Allowed PostgreSQL ENUM Values:

                        - `host_type`: Exactly one of:

                        * 'hoa_event'

                        * 'food_truck'

                        * 'paid_fitness'

                        * 'homeowner_hosted'

                        * 'hoa_announcement'

                        * 'community'

                        (Match using the visual color legend: Purple = 'hoa_event', Orange = 'food_truck', Blue = 'paid_fitness', Pink = 'homeowner_hosted', Green = 'hoa_announcement', Bottom Section = 'community')



                        - `audience_tag`: Exactly one of:

                        * 'kids_friendly'

                        * 'adult_friendly'

                        * 'all_ages'

                        * 'unspecified'



                        ### Extraction Rules:

                        1. Community & Date: Extract the month and year from the header (e.g., September 2026). Format dates as `YYYY-MM-DD`. `community_id` is always 'wolf_ranch'.

                        2. Timezone & Parsing: The location is Georgetown, TX (Central Time, UTC-5 during Daylight Saving Time). Convert start/end times into standard UTC ISO-8601 strings (`YYYY-MM-DDTHH:MM:SSZ`). If no end time is stated, set `end_time_utc` to `null`.

                        3. Title & Description: Clean the title (omit prices, times, and RSVP tags). Put sub-details, performers, food vendors, or competition rules into `description`.

                        4. Booleans:

                        - `fee_required`: `true` if any dollar amount (e.g., $17) or "Paid" tag is mentioned; otherwise `false`.

                        - `rsvp_required`: `true` if "RSVP", "Register", or "App" is explicitly listed; otherwise `false`.

                        - `is_all_day`: `true` for all-day closures or full-day events without a specific time; otherwise `false`.

                        - `is_kids_friendly`: `true` if suitable for kids/families.

                        - `is_adult_friendly`: `true` for general/adult activities.

                        5. Location: Extract shorthand locations and normalize where appropriate (e.g., "RC" -> "River Camp", "Den" -> "The Den").

                        6. Ambiguity Handling: If `audience_tag` cannot be inferred with high certainty from the title or description, set it to `'unspecified'` and list the event in the validation section below the JSON.



                        ### Output Format:

                        Output ONLY valid JSON inside a standard ```json code block.

                        Directly beneath the code block, if any events had an ambiguous audience, provide a short section titled "### Validation Required" listing:

                        - Date | Event Title | Guessed Tag | Question/Reason

                        If there are no ambiguities, do not include the section.



                        ### Output JSON Schema:

                        [

                        {

                        "community_id": "wolf_ranch",

                        "event_date": "YYYY-MM-DD",

                        "day_of_week": "Monday",

                        "start_time_utc": "YYYY-MM-DDTHH:MM:SSZ",

                        "end_time_utc": "YYYY-MM-DDTHH:MM:SSZ",

                        "is_all_day": false,

                        "title": "String",

                        "description": "String",

                        "location": "String",

                        "host_type": "hoa_event",

                        "fee_required": false,

                        "rsvp_required": false,

                        "audience_tag": "all_ages",

                        "is_kids_friendly": true,

                        "is_adult_friendly": true,

                        "notes": "String"

                        }

                        ] 


                        """
                    ),
                },
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Vision extraction returned an empty response.")
        parsed = json.loads(content)
        events = parsed.get("events")
        if not isinstance(events, list):
            raise ValueError("Vision extraction did not return an events array.")
        return [event for event in events if isinstance(event, dict)]
