(function attachNumberFormatters(windowObj) {
  const locale = "es-AR";

  function toFiniteNumber(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : 0;
  }

  function formatNumberAr(value, decimals = 2) {
    return toFiniteNumber(value).toLocaleString(locale, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  }

  function formatCurrencyAr(value, decimals = 2, symbol = "$") {
    const number = toFiniteNumber(value);
    const sign = number < 0 ? "-" : "";
    return `${sign}${symbol}${formatNumberAr(Math.abs(number), decimals)}`;
  }

  windowObj.formatNumberAr = formatNumberAr;
  windowObj.formatCurrencyAr = formatCurrencyAr;
})(window);
