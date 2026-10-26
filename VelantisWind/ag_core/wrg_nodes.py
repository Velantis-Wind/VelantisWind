"""Shared structural parsing of whitespace-delimited WRG node records."""
import math

from .log_text import log_error, log_text


def wrg_error(template, *, source="WRG", line_number=None, **data):
    """Translate error templates before inserting file names and numeric data.

    Qt stays optional for the scientific readers. Keep the template on the
    exception too, as other ag_core errors do, so UI consumers can show it in
    the active language even if that language changed since the error arose.
    """
    reason = log_text(template, **data)
    if line_number is None:
        return log_error(ValueError, "{source}: {reason}", source=source, reason=reason)
    return log_error(ValueError, "{source}, línea {line}: {reason}", source=source, line=line_number, reason=reason)


def node_tokens(tokens, *, source="WRG", line_number=None, nsec_expected=None):
    """Validate record structure, without converting or scaling climate values.

    A record has exactly 8 + 3*N fields, or 9 + 3*N with a single-token ID.
    Finite numeric IDs are deliberately unsupported: otherwise a numeric field
    added to a record without an ID can make its X look like an ID and shift the
    climate. Text and nonfinite-looking IDs (nan/inf) remain supported.
    This cannot detect damage that happens to form another accepted record.
    Callers validate the numeric values in their own conversion path.
    """
    def error(template, **data):
        return wrg_error(template, source=source, line_number=line_number, **data)

    # The two supported field counts have different remainders modulo three.
    offset = (len(tokens) - 8) % 3
    if offset not in (0, 1) or len(tokens) < offset + 11:
        raise error("Fila WRG inválida: el número de campos no coincide con los sectores declarados.")
    count = (len(tokens) - offset - 8) // 3
    try:
        declared = float(tokens[offset + 7])
    except ValueError:
        declared = float("nan")
    if declared != count:
        raise error("Fila WRG inválida: el número de campos no coincide con los sectores declarados.")
    if offset:
        try:
            numeric_id = math.isfinite(float(tokens[0]))
        except ValueError:
            numeric_id = False
        if numeric_id:
            raise error(
                "Identificador WRG convertible a número finito no admitido: "
                "puede confundirse con los datos de una fila sin identificador."
            )
    if nsec_expected is not None and count != nsec_expected:
        raise error("Nº sectores inconsistente: esperado {expected}, leído {actual}.",
                    expected=nsec_expected, actual=count)
    return (tokens[1:] if offset else tokens), offset
