from typing import Any
from typing import Dict
from typing import List

from reporting import settings
from reporting.schema.reporting_config import ReportingConfig
from reporting.schema.reporting_config import ScheduledQueryAction

_MODULES = {}


class ModuleInterface:
    """
    Type interface for modules.
    """

    @staticmethod
    def action_name() -> str:
        """
        The name of this action module, which will be referenced from within the
        scheduled query configuration, via the ``action_type`` setting. For example:

        .. highlight:: yaml

              images-with-no-scan:
                name: K8s container images with no vulnerability scans
                cypher: k8s-images-without-scans
                watch_scans:
                  - grouptype: KubernetesCluster
                    syncedtype: KubernetesCluster
                enabled: True
                actions:
                  # this will match an action module with the action_name of sqs
                  - action_type: sqs
                    action_config:
                      sqs_queue: k8s-image-scanner

        """
        return ""

    @staticmethod
    def setup(config: ReportingConfig) -> None:
        """
        Called when the scheduled queries worker is started. This function
        can be used for any setup that your module may need to do, like creating
        databases or queues in development, etc.
        """
        return

    @staticmethod
    def handle_results(
        scheduled_query_id: str,
        action: ScheduledQueryAction,
        results: List[Dict[str, Any]],
    ) -> None:
        """
        Called when a schedule query configured to use this module has results.
        """
        return


def load_modules(config: ReportingConfig) -> None:
    global _MODULES

    for module_name in settings.SCHEDULED_QUERY_MODULES:
        # fromlist is required here, or the module will not be loaded.
        # The actual valud of fromlist doesn't matter. We're using this rather
        # than importlib to be able to handle the type checking properly.
        module: ModuleInterface = __import__(module_name, fromlist=["_fake"])
        module.setup(config)
        _MODULES[module.action_name()] = module


def get_module_names() -> List[str]:
    return list(_MODULES.keys())


def get_module(action_name: str) -> ModuleInterface:
    global _MODULES

    return _MODULES[action_name]
