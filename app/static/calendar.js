"use strict";
window.ledgerCalendar = Object.freeze({
  bounds(month) {
    if (!/^[0-9]{4}-[0-9]{2}$/.test(month))
      throw new RangeError("Invalid month");
    const [year, index] = month.split("-").map(Number);
    if (year < 1 || year > 9999 || index < 1 || index > 12)
      throw new RangeError("Invalid month");
    const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
    const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][
      index - 1
    ];
    return { min: month + "-01", max: month + "-" + days };
  },
});
