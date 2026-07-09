import { describe, expect, it } from "vitest";
import { formatBRL, issueTypeLabel, severityClass } from "./utils";

describe("utils", () => {
  it("formats BRL", () => {
    expect(formatBRL(10)).toContain("10");
  });

  it("maps issue types", () => {
    expect(issueTypeLabel("missing_payment")).toBe("Pagamento ausente");
  });

  it("returns severity classes", () => {
    expect(severityClass("critical")).toContain("red");
  });
});
