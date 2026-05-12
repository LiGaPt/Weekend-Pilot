class AMapProviderError(RuntimeError):
    pass


class AMapConfigurationError(AMapProviderError):
    pass


class AMapUnsupportedToolError(AMapProviderError):
    pass
