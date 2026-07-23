from abc import ABC, abstractmethod

class BaseTemplateParser(ABC):

    @abstractmethod
    def parse(self, file_path):
        pass