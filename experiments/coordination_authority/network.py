"""Contain experimental agents' egress while retaining minimal-eval transport.

The installed Modal SDK exposes this policy replacement API. minimal-eval does
not yet expose it, so the private-adapter coupling is contained in this helper.
"""
ALLOWED_DOMAINS = ['api.z.ai']


def restrict_egress(sandbox):
    sandbox._sandbox._experimental_set_outbound_network_policy(
        outbound_cidr_allowlist=[], outbound_domain_allowlist=ALLOWED_DOMAINS)
    return {'outbound_cidr_allowlist': [], 'outbound_domain_allowlist': ALLOWED_DOMAINS}
