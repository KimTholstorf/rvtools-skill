"""Cloud-provider pricing adapters used by the BOM engine."""

from .azure import AzurePricingAdapter
from .google import GooglePricingAdapter
from .oci import OciPricingAdapter


def adapter_for(provider, **kwargs):
    provider = str(provider).strip().casefold()
    adapters = {
        "ocvs": OciPricingAdapter,
        "avs": AzurePricingAdapter,
        "gcve": GooglePricingAdapter,
    }
    if provider not in adapters:
        raise ValueError(f"unsupported BOM target: {provider}")
    return adapters[provider](**kwargs)


__all__ = ["adapter_for", "AzurePricingAdapter", "GooglePricingAdapter", "OciPricingAdapter"]
