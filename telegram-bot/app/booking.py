import base64
import json
import logging
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests

from config import TAX_CODE, HEALTH_CARD, BOOKING_BASE_URL, PROVINCES, TIMEZONE


# The field names sent to the booking website are Italian because they are part of its API

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"

# ISTAT codes the website uses to identify the provinces of Lombardy
PROVINCE_CODES = {
    "VA": "012", "CO": "013", "SO": "014", "MI": "015", "BG": "016", "BS": "017",
    "PV": "018", "CR": "019", "MN": "020", "LC": "097", "LO": "098", "MB": "108",
}

ERROR_MESSAGES = {
    "AUTH.INVALID.SESSION": "Session expired, the bot will log in again on the next check",
    "CRS.KO": "Health card not found, check TAX_CODE and HEALTH_CARD in the .env file",
    "CRS.NON.ATTIVA": "The health card is not active",
    "RICETTA.RICERCA.KO": "Prescription not found",
    "RICETTA.NON.TROVATA.MESSAGE": "Prescription not found",
    "RICETTA.RICERCA.FUORI.REGIONE.KO": "This prescription can't be booked online",
    "RICETTA.RICERCA.FARMACEUTICA": "This is a pharmaceutical prescription, it can't be booked",
    "RICETTA.SCADUTA.MESSAGE": "The prescription has expired",
    "RICETTA.NON.PRENOTABILE.MESSAGE": "The service in this prescription can't be booked right now",
    "RICETTA.PRENOTATA.MESSAGE": "The prescription has already been booked",
    "DISPONIBILITA.KO.MESSAGE": "No suitable availability online, call the regional Contact Center",
}


class BookingError(Exception):
    def __init__(self, code, message=None):
        self.code = code
        super().__init__(message or ERROR_MESSAGES.get(code) or f"The booking website returned an error ({code})")


def normalize_code(code):
    code = re.sub(r"[\s-]", "", code).upper()
    return code


def _is_iup(code):
    if len(code) != 10 or not re.fullmatch(r"[A-Z0-9]*([A-Z][0-9]|[0-9][A-Z])[A-Z0-9]*", code):
        return False
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    total = sum(alphabet.index(c) for c in code[:9])
    return alphabet[total % 36] == code[9]


def classify_code(code):
    """Returns the field name the backend expects for this kind of prescription code."""
    if re.fullmatch(r"R[A-Z0-9]{10}", code):
        return "iurp"
    if re.fullmatch(r"[A-Z0-9]{15}", code) and not code.isdigit():
        return "nre"
    if re.fullmatch(r"030\d{12}", code) and sum(int(c) for c in code[5:14]) % 9 == int(code[14]):
        return "rur"
    if _is_iup(code):
        return "iup"
    return None


class BookingClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.token = None
        self.info_header = None

    def _call(self, destination, arg):
        headers = {
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "X-Prenota-Online-Channel": "WEB",
        }
        if self.token:
            headers["X-Prenota-Online-Token"] = self.token
        if self.info_header:
            headers["X-Prenota-Online-Info"] = self.info_header

        data = {
            "metadata": json.dumps({"destination": destination, "method": "handle",
                                    "argumentTypes": ["java.lang.String"]}),
            "jsonBusinessArg0": json.dumps(arg).replace("&", "&amp;"),
        }
        resp = self.session.post(BOOKING_BASE_URL + "jsonBroker", data=data, headers=headers, timeout=60)
        resp.raise_for_status()
        body = resp.json()

        exception = body.get("exception")
        if exception:
            code = exception.get("code") or "UNKNOWN"
            logging.warning("%s failed: %s", destination, exception)
            raise BookingError(code)

        result = body.get("result")
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except ValueError:
                pass
        return result

    def open_session(self):
        # Passes through the Queue-it waiting room, which sets the cookies needed by the API
        resp = self.session.get(BOOKING_BASE_URL, timeout=60)
        if urlparse(resp.url).netloc != urlparse(BOOKING_BASE_URL).netloc:
            raise RuntimeError("The website is busy and placed the bot in the waiting room")

        self.token = self._call("pgpcitt_genera_token", {})

        params = self._call("pgpcitt_ricerca_parametro", {"formato": "CRIPTATO"})
        # Parameter values are only base64 encoded
        params = {p["nome"]: base64.b64decode(p["valore"]).decode() for p in params if p.get("valore")}
        self.info_header = f"{params.get('release.version', '')}|Linux|unknown|Chrome 130.0.0.0"
        self.separator = params.get("token.separator", " | ")

    def login(self):
        login_data = {"codiceFiscale": TAX_CODE, "crs": HEALTH_CARD,
                      "dataScadenza": "", "flagIncludiCrsNonAttive": "N"}
        user = self._call("pgpcitt_login_gp_prv", login_data)

        # The website appends the citizen's credentials to the session token after login
        self.token = self.separator.join([self.token, TAX_CODE, HEALTH_CARD])
        return user["cittadino"]

    def search_prescription(self, code, kind):
        criteria = {
            "codiceFiscale": TAX_CODE,
            "iup": None, "iurp": None, "nre": None, "rur": None,
            "periodo": {"dal": None, "al": None},
            "flagFlussoPostoInCoda": "N",
            "flagIncludiNonPrenotabili": "N",
            "codicePrestazione": "",
            "categoriaPrestazione": "",
        }
        criteria[kind] = code

        prescriptions = (self._call("pgpcitt_ricerca_ricetta", criteria) or {}).get("ricette") or []
        for prescription in prescriptions:
            module_id = (prescription.get("modulo") or {}).get("id")
            if code in (prescription.get("iup"), prescription.get("iurp"), module_id):
                return prescription
        if prescriptions:
            return prescriptions[0]
        raise BookingError("RICETTA.RICERCA.KO")

    def unlock_prescription(self, nre):
        # Searching an electronic prescription locks it, the website always unlocks it on exit
        self._call("pgpcitt_sblocca_ricetta_elettronica", {"codiceFiscale": TAX_CODE, "nre": nre})

    def find_zones(self, provinces):
        """Returns the search zones of the given provinces, Milano has one for the city and one for the province."""
        codes = {PROVINCE_CODES[p] for p in provinces if p in PROVINCE_CODES}
        zones = self._call("pgpcitt_ricerca_zona", {}) or []

        return [{
            "descrizione": z.get("descrizione"),
            "codiceProvincia": z.get("codiceProvincia"),
            "codiceComune": z.get("codiceComune"),
            "codice": f"{z.get('codiceProvincia')}{z.get('codiceComune')}",
            "abilitazionePiuPiu": z.get("abilitazionePiuPiu"),
            "abilitazioneNre": z.get("abilitazioneNre"),
        } for z in zones if z.get("codiceProvincia") in codes]

    def search_availability(self, citizen, prescription, zone):
        today = datetime.now(ZoneInfo(TIMEZONE)).replace(hour=0, minute=0, second=0, microsecond=0)

        prescription = dict(prescription)
        prescription["appuntamentiUnificati"] = None

        criteria = {
            "codiceFiscale": TAX_CODE,
            "zona": zone,
            "ricetta": prescription,
            "tipoPrestazione": guess_visit_type(prescription),
            "presidi": [],
            "aziende": [],
            "recapiti": {"telefono": citizen.get("telefono"), "cellulare": None, "email": citizen.get("email")},
            "vincoliTemporali": {
                "dal": today.strftime("%Y%m%d%H%M%S"), "al": None,
                "lunedi": "S", "martedi": "S", "mercoledi": "S", "giovedi": "S",
                "venerdi": "S", "sabato": "S", "domenica": "S",
                "mattina": "S", "pomeriggio": "S",
            },
            "caricaRequestRicercaAgende": "N",
            "minDal": None,
            "ats": None,
            "tipoNegoziazione": None,
            "regimeErogazione": None,
            "risorsa": None,
            "codiceProvincia": None,
            "codiceComune": None,
            "codiceStruttura": None,
            "equipe": None,
            "soggettoPagante": None,
        }
        return self._call("pgpcitt_ricerca_disponibilita", criteria) or {}


def guess_visit_type(prescription):
    """Same logic the website uses to decide between first visit ("O"), follow-up ("Z") and urgent ("U")."""
    if prescription.get("tipoPrestazione"):
        return prescription["tipoPrestazione"]
    if (prescription.get("priorita") or "P") == "U":
        return "U"

    visit_type = None
    for service in prescription.get("prestazioni") or []:
        description = re.sub(r"\s", "", service.get("descrizione") or "")
        if "(PRIMAVISITA)" in description:
            visit_type = "O"
        if "(CONTROLLO)" in description:
            visit_type = "Z"
        if visit_type is None and prescription.get("flagEsenzionePatologia") == "S":
            visit_type = "Z"

    # The website asks the user when it can't tell, default to first visit
    return visit_type or "O"


def parse_date(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, timezone.utc).astimezone(ZoneInfo(TIMEZONE))
    if isinstance(value, str):
        if re.fullmatch(r"\d{14}", value):
            return datetime.strptime(value, "%Y%m%d%H%M%S").replace(tzinfo=ZoneInfo(TIMEZONE))
        if re.fullmatch(r"\d{8}", value):
            return datetime.strptime(value, "%Y%m%d").replace(tzinfo=ZoneInfo(TIMEZONE))
        if value.isdigit():
            return parse_date(int(value))
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=ZoneInfo(TIMEZONE))
            return parsed.astimezone(ZoneInfo(TIMEZONE))
        except ValueError:
            return None
    return None


def _format_address(point):
    if not point:
        return ""
    address = point.get("indirizzo") or {}
    location = point.get("localita") or {}

    street = " ".join(str(p) for p in (address.get("toponimo"), address.get("descrizione"),
                                         address.get("civico")) if p)
    city = location.get("descrizione") or ""
    if location.get("siglaProvincia"):
        city += f" ({location['siglaProvincia']})"
    return ", ".join(p for p in (street, city) if p)


def extract_slots(availability):
    slots = []

    entries = list(availability.get("singole") or [])
    for group in (availability.get("combinate") or []) + (availability.get("associate") or []):
        if group.get("lista"):
            entries.append(group["lista"][0])

    for entry in entries:
        appointment = entry.get("appuntamento") or {}
        date = parse_date(appointment.get("data"))
        if date is None:
            continue

        unit = appointment.get("unitaErogante") or appointment.get("unitaErogatrice") or {}
        facility = unit.get("presidio") or {}
        company = facility.get("azienda") or appointment.get("azienda") or {}

        point = facility.get("puntoIndirizzo") or unit.get("puntoIndirizzo") or {}
        slots.append({
            "date": date,
            "place": facility.get("descrizione") or unit.get("descrizione") or "",
            "company": company.get("descrizione") or "",
            "address": _format_address(point),
            "province": (point.get("localita") or {}).get("siglaProvincia"),
        })

    slots.sort(key=lambda s: s["date"])
    return slots


def check_prescription(code, retries=3, backoff=10):
    """Logs in, looks up the prescription and returns (service description, sorted list of free slots)."""
    kind = classify_code(code)
    if kind is None:
        raise BookingError("CODE.INVALID", "Invalid prescription code")

    for attempt in range(retries + 1):
        client = BookingClient()
        try:
            client.open_session()
            citizen = client.login()

            prescription = client.search_prescription(code, kind)
            slots = {}
            try:
                for zone in client.find_zones(PROVINCES):
                    for slot in extract_slots(client.search_availability(citizen, prescription, zone)):
                        if slot["province"] in PROVINCES:
                            slots[(slot["date"], slot["place"])] = slot
            finally:
                nre = (prescription.get("modulo") or {}).get("id") if kind != "nre" else code
                if nre and classify_code(nre) == "nre":
                    try:
                        client.unlock_prescription(nre)
                    except Exception as e:
                        logging.warning("Unable to unlock prescription %s: %r", nre, e)

            description = ", ".join(p.get("descrizione") or "" for p in prescription.get("prestazioni") or [])
            return description, sorted(slots.values(), key=lambda s: s["date"])

        except BookingError:
            raise

        except Exception as e:
            logging.warning("Attempt %d failed for prescription %s: %r", attempt + 1, code, e)

            if attempt < retries:
                time.sleep(backoff)
            else:
                raise
