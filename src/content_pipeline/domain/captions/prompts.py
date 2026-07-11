"""Provider-independent prompt construction."""

import json

from content_pipeline.domain.captions.models import (
    CaptionPrompt,
    CaptionTask,
    PromptRequest,
)
from content_pipeline.domain.models.json import thaw_json_value


class PromptBuilder:
    """Build deterministic prompt values without knowing a provider's API."""

    def build(self, request: PromptRequest) -> CaptionPrompt:
        """Build a neutral prompt for any supported caption task."""
        context = [
            f"Task: {request.task.value}",
            f"Language: {request.language}",
            f"Subject: {request.subject}",
        ]
        if request.platform is not None:
            context.append(f"Platform: {request.platform}")
        if request.tone is not None:
            context.append(f"Tone: {request.tone}")
        if request.style is not None:
            context.append(f"Style: {request.style}")
        if request.target_length is not None:
            context.append(f"Target length: {request.target_length} characters")
        if request.custom_variables:
            variables = json.dumps(
                thaw_json_value(request.custom_variables),
                ensure_ascii=False,
                sort_keys=True,
            )
            context.append(f"Custom variables: {variables}")
        return CaptionPrompt(
            task=request.task,
            system_instruction=(
                "Produce only content that satisfies the requested task."
            ),
            user_instruction="\n".join(context),
            language=request.language,
            platform=request.platform,
        )

    def build_from_prompt(self, prompt: CaptionPrompt) -> CaptionPrompt:
        """Return a fresh neutral prompt when a request already owns one.

        ``CaptionRequest`` deliberately stores the provider-neutral prompt rather
        than the prompt-building inputs. Rebuilding this value preserves all of
        its context without inventing or losing source fields.
        """
        return CaptionPrompt(
            task=prompt.task,
            system_instruction=prompt.system_instruction,
            user_instruction=prompt.user_instruction,
            language=prompt.language,
            platform=prompt.platform,
        )

    def build_title(self, request: PromptRequest) -> CaptionPrompt:
        """Build a title-generation prompt from title-specific inputs."""
        return self.build(_with_task(request, CaptionTask.TITLE))

    def build_caption(self, request: PromptRequest) -> CaptionPrompt:
        """Build a caption-generation prompt from caption-specific inputs."""
        return self.build(_with_task(request, CaptionTask.CAPTION))

    def build_description(self, request: PromptRequest) -> CaptionPrompt:
        """Build a description-generation prompt from description-specific inputs."""
        return self.build(_with_task(request, CaptionTask.DESCRIPTION))

    def build_hashtags(self, request: PromptRequest) -> CaptionPrompt:
        """Build a hashtag-generation prompt from hashtag-specific inputs."""
        return self.build(_with_task(request, CaptionTask.HASHTAGS))


def _with_task(request: PromptRequest, task: CaptionTask) -> PromptRequest:
    """Copy prompt input with an explicit task without mutating caller state."""
    return PromptRequest(
        task=task,
        subject=request.subject,
        language=request.language,
        tone=request.tone,
        style=request.style,
        target_length=request.target_length,
        platform=request.platform,
        custom_variables=request.custom_variables,
    )
