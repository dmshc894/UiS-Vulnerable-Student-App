import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urljoin, urlsplit

MAX_URL_LENGHT = 2048
MAX_PREVIEW_BYTES = 2000
MAX_REDIRECTS = 3
TIMEOUT_SECONDS = 5

class RessourceFetchError(Exception):
    pass


def _parse_url(url:str):

    if not isinstance(url,str) or not url or len(url)>MAX_URL_LENGHT:
        raise RessourceFetchError("Invalid resource URL")
    if any(ord(ch) < 33 or ord(ch) == 127 for ch in url) or "\\" in url:
        raise RessourceFetchError("Invalid resource url")

    try:
        parts = urlsplit(url)
        host = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise RessourceFetchError("Invalid resource URL") from exc

    if parts.scheme not in ("http","https") or not host or not parts.netloc:
        raise RessourceFetchError("Only HTTPS and HTTP URLs are supported")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise RessourceFetchError("Credentials in URLs are not allowe")

    if "%" in parts.netloc or "#" in parts.netloc:
        raise RessourceFetchError("invalid resource host")

    expected_port = 443 if parts.scheme == "https" else 80
    if port is not None and port != expected_port:
        raise RessourceFetchError("Only HTTP/HTTPS ports allowed")

    try: 
        host = host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise RessourceFetchError("Invalid resource host") from exc

    return parts, host, expected_port


def _resolve_public_ip(host: str, port: int) -> str:
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc: 
        raise RessourceFetchError("Unable to resolve resource host") from exc

    if not addresses:
        raise RessourceFetchError ("Unable to resolve resourse host")

    public_ips = []
    for entry in addresses:
        try:
            ip = ipaddress.ip_address(entry[4][0])
        except ValueError as exc:
            raise RessourceFetchError("Invalid resolved IP address") from exc
        if not ip.is_global:
            raise RessourceFetchError("Internal network addressses are blocked")
        public_ips.append(str(ip))

    return public_ips[0]
    

def _request_once(url: str):
    parts, host, port = _parse_url(url)
    ip = _resolve_public_ip(host, port)
    conn = None
    raw_sock = None

    try:
        raw_sock = socket.create_connection((ip,port), timeout=TIMEOUT_SECONDS)
        raw_sock.settimeout(TIMEOUT_SECONDS)
        if parts.scheme == "https":
            context = ssl.create_default_context()
            sock = context.wrap_socket(raw_sock,server_hostname=host)
            raw_sock = None
            conn = http.client.HTTPSConnection(host,port,timeout=TIMEOUT_SECONDS,context=context)
        else:
            sock = raw_sock
            raw_sock = None
            conn = http.client.HTTPConnection(host,port,timeout=TIMEOUT_SECONDS)


        conn.sock = sock
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        conn.request("GET",path,headers={
            "Accept-Encoding": "identity",
            "Connection": "close",
            "User-Agent": "DAT250-SecyreApp-ResourceImporter/1.0"
        })

        response = conn.getresponse()
        if response.status in (301,302,303,307,308):
            location = response.getheader("Location")
            if not location:
                raise RessourceFetchError("Resource redirected without destination")
            return None, urljoin(url,location)

        if not 200 <= response.status <300:
            raise RessourceFetchError("Remote resource returned HTTP %d" %response.status)

        data = response.read(MAX_PREVIEW_BYTES)
        charset = response.headers.get_content_charset() or "utf-8"
        try:
            body = data.decode(charset,errors="replace")
        except (LookupError, UnicodeError):
            body = data.decode("utf-8", errors="replace")

        return body, None
    except (OSError,ssl.SSLError, http.client.HTTPException, ValueError) as exc:
        raise RessourceFetchError("Unable to find external resource") from exc
    finally:
        if conn is not None:
            conn.close()
        if raw_sock is not None:
            raw_sock.close()


def fetch_public_resource(url: str) -> str:
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        body, redirect_to = _request_once(current)
        if redirect_to is None:
            return body
        current = redirect_to
    raise RessourceFetchError("Too many redirects")

        