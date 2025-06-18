from typing import Union, Any, Optional
from copy import deepcopy
from util.logging import log

logger = log()
global_artifacts: list[Any] = []

def set_artifact(artifact: Any) -> None:
    """
    Set an artifact to the global artifacts list.
    :param artifact: The artifact to set.
    """
    global global_artifacts
    global_artifacts.append(deepcopy(artifact))
    logger.debug(f"Artifact set: {str(type(artifact))}")

def get_artifact_from_type(artifact_type: Union[type, Any]) -> Optional[Any]:
    """
    Get an artifact from the global artifacts list by its type.
    :param artifact_type: The type of the artifact to get.
    :return: The artifact if found, None otherwise.
    """
    global global_artifacts
    for artifact in global_artifacts:
        if isinstance(artifact, artifact_type):
            return artifact
    return None

