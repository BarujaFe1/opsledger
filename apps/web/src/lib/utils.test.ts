import { describe, expect, it } from "vitest";
import { formatBRL, issueImpactLabel, issueTypeLabel, severityClass, statusLabel } from "./utils";
import { parseBatchId, parsePositiveInt } from "./routing";

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

describe("parseBatchId", () => {
  it("accepts positive integers (real batches)", () => {
    expect(parseBatchId("1")).toBe(1);
    expect(parseBatchId("150")).toBe(150);
  });

  it("accepts the demo sentinel -1 (public demo contract)", () => {
    expect(parseBatchId("-1")).toBe(-1);
  });

  it("rejects zero, below-sentinel negatives, non-integers and junk", () => {
    expect(parseBatchId("0")).toBeNull();
    expect(parseBatchId("-2")).toBeNull();
    expect(parseBatchId("abc")).toBeNull();
    expect(parseBatchId("1.5")).toBeNull();
    expect(parseBatchId("")).toBeNull();
  });
});

describe("issueImpactLabel", () => {
  it("labels monetary issues as 'Impacto financeiro'", () => {
    expect(issueImpactLabel("missing_payment")).toBe("Impacto financeiro");
    expect(issueImpactLabel("orphan_payment")).toBe("Impacto financeiro");
    expect(issueImpactLabel("amount_mismatch")).toBe("Impacto financeiro");
    expect(issueImpactLabel("duplicate_line")).toBe("Impacto financeiro");
    expect(issueImpactLabel("header_conflict")).toBe("Impacto financeiro");
  });

  it("labels stock / data-quality issues as 'Valor associado'", () => {
    expect(issueImpactLabel("missing_stock_out")).toBe("Valor associado");
    expect(issueImpactLabel("negative_stock")).toBe("Valor associado");
    expect(issueImpactLabel("channel_standardization")).toBe("Valor associado");
  });
});
