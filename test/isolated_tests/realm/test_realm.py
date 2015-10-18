import pytest

from yosai import (
    AccountStoreRealm,
    CacheCredentialsException,
    ClearCacheCredentialsException,
    GetCachedCredentialsException,
    IncorrectCredentialsException,
    PasswordMatcher,
    RealmMisconfiguredException,
)
from ..doubles import (
    MockAccount,
    MockAccountStore,
    MockCache,
)

from .doubles import (
    MockCredentialsCacheHandler,
    MockCredentialsCacheResolver,
)

from unittest import mock

# -----------------------------------------------------------------------------
# AccountStoreRealm Tests
# -----------------------------------------------------------------------------

def test_asr_do_clear_cache(patched_accountstore_realm):
    """
    unit tested:  do_clear_cache

    test case:
    in turn calls the clear cache methods for credentials and authz info
    """
    asr = patched_accountstore_realm
    with mock.patch.object(AccountStoreRealm, 'clear_cached_credentials') as ccc:
        ccc.return_value = None

        with mock.patch.object(AccountStoreRealm,
                               'clear_cached_authorization_info') as ccai:
            ccai.return_value = None

            asr.do_clear_cache('identifiers')

            ccc.assert_called_once_with('identifiers')
            ccai.assert_called_once_with('identifiers')


def test_asr_clear_cached_credentials(patched_accountstore_realm, monkeypatch):
    """
    unit tested: clear_cached_credentials

    test case:
    delegates to cch.clear_cache
    """
    asr = patched_accountstore_realm
    cch = mock.MagicMock() # credentials_cache_handler
    monkeypatch.setattr(asr, 'credentials_cache_handler', cch)
    asr.clear_cached_credentials('identifiers')
    assert cch.method_calls[0] == mock.call.clear_cache('identifiers')

def test_asr_clear_cached_authorization_info(
        patched_accountstore_realm, monkeypatch):
    """
    unit tested: clear_cached_authorization_info

    test case:
    delegates to ach.clear_cache
    """
    asr = patched_accountstore_realm
    ach = mock.MagicMock() # credentials_cache_handler
    monkeypatch.setattr(asr, 'authorization_cache_handler', ach)
    asr.clear_cached_authorization_info('identifiers')
    assert ach.method_calls[0] == mock.call.clear_cache('identifiers')


def test_asr_supports(patched_accountstore_realm,
                      mock_token,
                      username_password_token):
    par = patched_accountstore_realm
    token = username_password_token
    mt = mock_token

    assert (par.supports(token) and not par.supports(mt))

def test_asr_get_credentials_misconfigured_raises(patched_accountstore_realm,
                                                  username_password_token,
                                                  monkeypatch):
    """
    unit tested:  get_credentials

    test case:
    a misconfigured AccountStoreRealm will raise an exception when
    get_credentials is attempted

    in this test, there is no accountstore attribute, and so the
    exception will raise
    """
    par = patched_accountstore_realm
    token = username_password_token
    monkeypatch.setattr(par, 'credentials_cache_handler', None)
    monkeypatch.setattr(par, 'account_store', None)

    with pytest.raises(RealmMisconfiguredException):
        par.authenticate_account(token)

def test_asr_get_credentials_with_cached_acct_succeeds(
        patched_accountstore_realm, monkeypatch, username_password_token):
    """
    unit tested:  get_credentials

    test case:
    MockCredentialsCacheHandler.get_cached_credentials returns a MockAccount
    """
    par = patched_accountstore_realm
    token = username_password_token
    result = par.get_credentials(token)
    assert result == MockAccount(account_id='MACH13579')


def test_asr_get_credentials_without_cached_acct_succeeds_and_caches(
        monkeypatch, username_password_token, patched_accountstore_realm):
    """
    unit tested:  get_credentials

    test case:
    If the account isn't cached, it should be obtained from the account_store.
    Since an CredentialsCacheHandler is set, the account is cached.

    CredentialsCacheHandler.get_cached_credentials returns None
    AccountStore.get_account returns a mock acount
    """
    token = username_password_token
    pasr = patched_accountstore_realm
    ach = pasr.credentials_cache_handler
    monkeypatch.setattr(pasr, '_credentials_cache_handler',
                        MockCredentialsCacheHandler(account=''))
    with mock.patch.object(MockCredentialsCacheHandler, 'cache_credentials') as cc:
        cc.return_value = None
        result = pasr.get_credentials(token)
        cc.assert_called_once_with(token, result)

        # the MockAccountStore's default account_id is MAS123:
        assert result.account_id == 'MAS123'


def test_asr_get_credentials_cannot_locate_account(username_password_token,
                                                   patched_accountstore_realm,
                                                   monkeypatch, capsys):
    """
    unit tested:  authenticate_account

    test case:
    in the event that an account cannot be found (for a token's parameters)
    from an account_store, None is returned from get_credentials

    CredentialsCacheHandler.get_cached_credentials returns None
    AccountStore.get_account returns None
    """
    token = username_password_token
    pasr = patched_accountstore_realm
    pasr.credentials_cache_handler = MockCredentialsCacheHandler(account=None)
    pasr.account_store = MockAccountStore(account=None)

    result = pasr.get_credentials(token)
    out, err = capsys.readouterr()
    assert result is None and 'No account found' in out


def test_asr_authenticate_account(username_password_token,
                                  patched_accountstore_realm,
                                  full_mock_account, monkeypatch):
    token = username_password_token
    pasr = patched_accountstore_realm
    fma = full_mock_account

    monkeypatch.setattr(pasr, 'get_credentials', lambda x: fma)
    with mock.patch.object(AccountStoreRealm, 'assert_credentials_match') as acm:
        acm.return_value = None
        with mock.patch.object(AccountStoreRealm, 'clear_cached_credentials') as ccc:
            ccc.return_value = None
            result = pasr.authenticate_account(token)
            acm.assert_called_once_with(token, fma)
            ccc.assert_called_once_with(token.identifier)
            assert result == fma


def test_asr_acm_succeeds(username_password_token, patched_accountstore_realm,
                          full_mock_account):
    """
    unit tested:  assert_credentials_match

    test case:
    when credentials match, nothing is returned nor any exceptions raise
    """
    token = username_password_token
    pasr = patched_accountstore_realm

    with mock.patch.object(PasswordMatcher, 'credentials_match') as pm_cm:
        pm_cm.return_value = True
        result = pasr.assert_credentials_match(token, full_mock_account)
        pm_cm.assert_called_once_with(token, full_mock_account)


def test_asr_acm_raises(username_password_token, patched_accountstore_realm,
                        full_mock_account):
    """
    unit tested:  assert_credentials_match

    test case:
    when credentials fail to match, an exception is raised
    """
    token = username_password_token
    pasr = patched_accountstore_realm

    with pytest.raises(IncorrectCredentialsException):
        with mock.patch.object(PasswordMatcher, 'credentials_match') as pm_cm:
            pm_cm.return_value = False
            pasr.assert_credentials_match(token, full_mock_account)


# -----------------------------------------------------------------------------
# DefaultCredentialsCacheHandler Tests
# -----------------------------------------------------------------------------

def test_dach_gca_fails_to_obtain_cache_resolver(
        patched_default_credentials_cache_handler, monkeypatch,
        username_password_token):
    """
    unit tested:  get_cached_credentials
    """

    pdach = patched_default_credentials_cache_handler
    token = username_password_token

    monkeypatch.setattr(pdach, 'credentials_cache_resolver', None)

    with pytest.raises(GetCachedCredentialsException):
        pdach.get_cached_credentials(token)

def test_dach_gca_fails_to_obtain_cache_key_resolver(
        patched_default_credentials_cache_handler, monkeypatch,
        username_password_token):
    """
    unit tested:  get_cached_credentials
    """

    pdach = patched_default_credentials_cache_handler
    token = username_password_token

    monkeypatch.setattr(pdach, 'credentials_cache_key_resolver', None)

    with pytest.raises(GetCachedCredentialsException):
        pdach.get_cached_credentials(token)

def test_dach_gca_fails_to_locate_cache(
        patched_default_credentials_cache_handler, monkeypatch,
        username_password_token):
    """
    unit tested:  get_cached_credentials

    test case:
    by default, the MockCredentialsCacheResolver returns None

    """

    pdach = patched_default_credentials_cache_handler
    token = username_password_token

    with pytest.raises(GetCachedCredentialsException):
        pdach.get_cached_credentials(token)


def test_dach_gca_fails_to_locate_cache_key(
        patched_default_credentials_cache_handler, monkeypatch,
        username_password_token, patched_mock_credentials_cache_resolver):
    """
    unit tested:  get_cached_credentials

    test case:
    the default pdach fixture uses empty mocks, therefore both the
        get_credentials_cache and get_credentials_cache_key return None

    the patched mock fixtures return values
    """

    pdach = patched_default_credentials_cache_handler  # doesn't matter if patched
    token = username_password_token
    pmacr = patched_mock_credentials_cache_resolver

    monkeypatch.setattr(pdach, 'credentials_cache_resolver', pmacr)

    result = pdach.get_cached_credentials(token)

    assert result is None


def test_dach_gca_fails_to_locate_cached_credentials(
        patched_default_credentials_cache_handler, monkeypatch,
        username_password_token, patched_mock_credentials_cache_resolver,
        patched_mock_credentials_cache_key_resolver):
    """
    unit tested:  get_cached_credentials
    """

    pdach = patched_default_credentials_cache_handler  # doesn't matter if patched
    token = username_password_token
    pmacr = patched_mock_credentials_cache_resolver
    pmackr = patched_mock_credentials_cache_key_resolver
    monkeypatch.setattr(pmackr, 'key', 'user223344')

    monkeypatch.setattr(pdach, 'credentials_cache_resolver', pmacr)
    monkeypatch.setattr(pdach, 'credentials_cache_key_resolver', pmackr)

    result = pdach.get_cached_credentials(token)

    assert result is None


def test_dach_gca_succeeds_in_locating_cached_credentials(
        patched_default_credentials_cache_handler, monkeypatch,
        username_password_token, patched_mock_credentials_cache_key_resolver):
    """
    unit tested:  get_cached_credentials
    """

    pdach = patched_default_credentials_cache_handler  # doesn't matter if patched
    token = username_password_token
    pmackr = patched_mock_credentials_cache_key_resolver

    # DG:  a username is presumably a good key to reference an account:
    key = token.username
    value = MockAccount(account_id='CachedAccount12345')
    pmacr = MockCredentialsCacheResolver(MockCache({key: value}))

    monkeypatch.setattr(pdach, 'credentials_cache_resolver', pmacr)

    # key is: 'CachedAccount12345'
    monkeypatch.setattr(pdach, 'credentials_cache_key_resolver', pmackr)

    result = pdach.get_cached_credentials(token)  # token is ignored by mock

    assert result.account_id == 'CachedAccount12345'

def test_dach_ca_fails_to_obtain_cache_resolver(
        patched_default_credentials_cache_handler, monkeypatch,
        username_password_token, full_mock_account):
    """
    unit tested:  cache_credentials
    """

    pdach = patched_default_credentials_cache_handler
    account = full_mock_account
    token = username_password_token
    monkeypatch.setattr(pdach, 'credentials_cache_resolver', None)

    with pytest.raises(CacheCredentialsException):
        pdach.cache_credentials(authc_token=token, account=account)

def test_dach_ca_fails_to_obtain_cache_key_resolver(
        patched_default_credentials_cache_handler, monkeypatch,
        patched_mock_credentials_cache_resolver,
        username_password_token, full_mock_account):
    """
    unit tested:  cache_credentials

    test case:
    the cache is obtained but the key isn't
    """

    pdach = patched_default_credentials_cache_handler
    account = full_mock_account
    token = username_password_token

    pmacr = patched_mock_credentials_cache_resolver
    monkeypatch.setattr(pdach, 'credentials_cache_resolver', pmacr)
    monkeypatch.setattr(pdach, 'credentials_cache_key_resolver', None)

    with pytest.raises(CacheCredentialsException):
        pdach.cache_credentials(authc_token=token, account=account)

def test_dach_ca_fails_to_locate_cache(
        patched_default_credentials_cache_handler, full_mock_account,
        username_password_token):
    """
    unit tested:  cache_credentials

    test case:
    by default, the MockCredentialsCacheResolver returns None
    """

    pdach = patched_default_credentials_cache_handler
    account = full_mock_account
    token = username_password_token

    with pytest.raises(CacheCredentialsException):
        pdach.cache_credentials(authc_token=token, account=account)


def test_dach_ca_fails_to_locate_cache_key(
        patched_default_credentials_cache_handler, monkeypatch,
        username_password_token, patched_mock_credentials_cache_resolver,
        full_mock_account):
    """
    unit tested:  cache_credentials

    test case:
    the default pdach fixture uses empty mocks, therefore both the
    get_credentials_cache and get_credentials_cache_key return None

    the patched mock fixtures return values
    """

    pdach = patched_default_credentials_cache_handler  # doesn't matter if patched
    account = full_mock_account
    token = username_password_token
    pmacr = patched_mock_credentials_cache_resolver

    monkeypatch.setattr(pdach, 'credentials_cache_resolver', pmacr)

    with pytest.raises(CacheCredentialsException):
        pdach.cache_credentials(authc_token=token, account=account)

def test_dach_ca_succeeds_in_caching_account(
        patched_default_credentials_cache_handler, monkeypatch,
        username_password_token, patched_mock_credentials_cache_key_resolver,
        patched_mock_credentials_cache_resolver, full_mock_account):
    """
    unit tested:  cache_credentials
    """

    pdach = patched_default_credentials_cache_handler  # doesn't matter if patched
    token = username_password_token
    account = full_mock_account  # has account_id = 8675309

    # pmackr always returns key='user123':
    pmackr = patched_mock_credentials_cache_key_resolver
    monkeypatch.setattr(pdach, 'credentials_cache_key_resolver', pmackr)

    pmacr = patched_mock_credentials_cache_resolver
    monkeypatch.setattr(pdach, 'credentials_cache_resolver', pmacr)

    pdach.cache_credentials(authc_token=token, account=account)

    # returns a full MockAccount:
    result = pdach.credentials_cache_resolver.cache.get('user123')
    assert result.account_id == 8675309


def test_dach_cca_fails_to_obtain_cache_resolver(
        patched_default_credentials_cache_handler, monkeypatch, full_mock_account):
    """
    unit tested:  clear_cached_credentials
    """

    pdach = patched_default_credentials_cache_handler
    account = full_mock_account
    monkeypatch.setattr(pdach, 'credentials_cache_resolver', None)

    with pytest.raises(ClearCacheCredentialsException):
        pdach.clear_cached_credentials(account_id=account.account_id)

def test_dach_cca_fails_to_obtain_cache_key_resolver(
        patched_default_credentials_cache_handler, monkeypatch,
        full_mock_account, patched_mock_credentials_cache_resolver):
    """
    unit tested:  clear_cached_credentials
    """

    pdach = patched_default_credentials_cache_handler
    account = full_mock_account

    pmacr = patched_mock_credentials_cache_resolver
    monkeypatch.setattr(pdach, 'credentials_cache_resolver', pmacr)
    monkeypatch.setattr(pdach, 'credentials_cache_key_resolver', None)

    with pytest.raises(ClearCacheCredentialsException):
        pdach.clear_cached_credentials(account_id=account.account_id)

def test_dach_cca_fails_to_locate_cache(
        patched_default_credentials_cache_handler, full_mock_account,
        username_password_token):
    """
    unit tested:  clear_cached_credentials

    by default, the MockCredentialsCacheResolver returns None
    """

    pdach = patched_default_credentials_cache_handler
    account = full_mock_account

    with pytest.raises(ClearCacheCredentialsException):
        pdach.clear_cached_credentials(account_id=account.account_id)

def test_dach_cca_fails_to_locate_cache_key(
        patched_default_credentials_cache_handler, monkeypatch,
        patched_mock_credentials_cache_resolver, full_mock_account):
    """
    unit tested:  clear_cached_credentials

    test case:
    the default pdach fixture uses empty mocks, therefore both the
    get_credentials_cache and get_credentials_cache_key return None

    the patched mock fixtures return values
    """

    pdach = patched_default_credentials_cache_handler  # doesn't matter if patched
    account = full_mock_account
    pmacr = patched_mock_credentials_cache_resolver

    monkeypatch.setattr(pdach, 'credentials_cache_resolver', pmacr)

    result = pdach.clear_cached_credentials(account_id=account.account_id)

    assert result is None


def test_dach_cca_succeeds_in_removing_cached_credentials(
        patched_default_credentials_cache_handler, monkeypatch,
        username_password_token, patched_mock_credentials_cache_key_resolver,
        patched_mock_credentials_cache_resolver, full_mock_account):
    """
    unit tested:  clear_cached_credentials
    """

    pdach = patched_default_credentials_cache_handler  # doesn't matter if patched
    account = full_mock_account  # has account_id = 8675309

    # pmackr always returns key='user123':
    pmackr = patched_mock_credentials_cache_key_resolver
    monkeypatch.setattr(pdach, 'credentials_cache_key_resolver', pmackr)

    # uses a MockCache:
    pmacr = patched_mock_credentials_cache_resolver
    monkeypatch.setattr(pdach, 'credentials_cache_resolver', pmacr)

    # returns a full MockAccount:
    result = pdach.clear_cached_credentials(account_id=account.account_id)

    assert result.account_id == 8675309
