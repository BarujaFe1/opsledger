import { describe, expect, it } from "vitest";
import { formatBRL, issueTypeLabel, severityClass, statusLabel } from "./utils";
import { parsePositiveInt } from "./routing";

describe("formatBRL", () => {
  it("formats BRL currency", () => {
    expect(formatBRL(10)).toMatch(/R\$\s?10/);
  });
});

describe("issueTypeLabel", () => {
  it("maps known types", () => {
    expect(issueTypeLabel("missing_payment")).toBe("Pagamento ausente");
  });
});

describe("severityClass", () => {
  it("returns critical styles", () => {
    expect(severityClass("critical")).toContain("red");
  });
});

describe("statusLabel", () => {
  it("translates status to PT-BR", () => {
    expect(statusLabel("reviewing")).toBe("Em revisão");
  });
});

describe("parsePositiveInt", () => {
  it("accepts positive integers", () => {
    expect(parsePositiveInt("12")).toBe(12);
    expect(parsePositiveInt(["3"])).toBe(3);
  });

  it("rejects invalid ids that used to hang loading", () => {
    expect(parsePositiveInt("abc")).toBeNull();
    expect(parsePositiveInt("0")).toBeNull();
    expect(parsePositiveInt("-1")).toBeNull();
    expect(parsePositiveInt(undefined)).toBeNull();
  });
});
