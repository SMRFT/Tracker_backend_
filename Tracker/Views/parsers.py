from rest_framework.parsers import MultiPartParser, FormParser

class MutableMultiPartParser(MultiPartParser):
    def parse(self, stream, media_type=None, parser_context=None):
        result = super().parse(stream, media_type, parser_context)
        if hasattr(result.data, '_mutable'):
            result.data._mutable = True
        return result

class MutableFormParser(FormParser):
    def parse(self, stream, media_type=None, parser_context=None):
        result = super().parse(stream, media_type, parser_context)
        if hasattr(result, '_mutable'):
            result._mutable = True
        return result
