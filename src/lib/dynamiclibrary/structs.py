import importlib
import inspect
from types import ModuleType
from util.logging import log

class DynamicLibrary:
    def __init__(self, module_name: str, module: ModuleType):
        self.module_name = module_name
        self.module = module
        self.signature: inspect.Signature = None

    def set_signature(self, func_name: str):
        if func_name != None:
            func = self.loadattr(func_name)
            self.signature = inspect.signature(func)

    def loadattr(self, attr_name: str):
        if self.module is None:
            raise ImportError(f"Module {self.module_name} not loaded")
        try:
            if hasattr(self.module, attr_name):
                return getattr(self.module, attr_name)
            else:
                return None
        except AttributeError as e:
            raise ImportError(f"Attribute {attr_name} not found in module {self.module_name}") from e

    def reload_module(self):
        try:
            self.module = importlib.reload(self.module)
            return self.module
        except ImportError as e:
            raise ImportError(f"Failed to reload module {self.module_name}: {e}")

    def list_attributes(self):
        if self.module is None:
            raise ImportError(f"Module {self.module_name} not loaded")
        return dir(self.module)
    
    def param_names(self):
        if self.module is None:
            raise ImportError(f"Module {self.module_name} not loaded")
        return list(self.signature.parameters.keys())
    
    def param_values(self):
        if self.module is None:
            raise ImportError(f"Module {self.module_name} not loaded")
        return self.signature.parameters.values()