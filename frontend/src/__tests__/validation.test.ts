import { describe, it, expect } from "vitest";
import {
  validateRegisterField,
  validateRegisterForm,
  type RegisterFormValues,
} from "@/lib/validation";

function makeValid(): RegisterFormValues {
  return {
    email: "valid@example.com",
    password: "Secure123",
    confirmPassword: "Secure123",
    fullName: "Valid User",
    companyName: "Valid Corp",
    industry: "technology",
    region: "US",
  };
}

describe("register validation", () => {
  it("accepts a valid form", () => {
    const values = makeValid();
    expect(validateRegisterForm(values)).toEqual({});
  });

  it("rejects invalid email format", () => {
    const values = makeValid();
    values.email = "not-an-email";
    expect(validateRegisterField("email", values)).toContain("valid email");
  });

  it("rejects weak password", () => {
    const values = makeValid();
    values.password = "short";
    values.confirmPassword = "short";
    expect(validateRegisterField("password", values)).toContain("at least 8");
  });

  it("rejects mismatched confirm password", () => {
    const values = makeValid();
    values.confirmPassword = "Mismatch123";
    expect(validateRegisterField("confirmPassword", values)).toContain("do not match");
  });
});
