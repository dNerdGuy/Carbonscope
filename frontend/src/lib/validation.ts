export interface RegisterFormValues {
  email: string;
  password: string;
  confirmPassword: string;
  fullName: string;
  companyName: string;
  industry: string;
  region: string;
}

export function validateRegisterField(
  field: keyof RegisterFormValues,
  values: RegisterFormValues,
): string {
  const value = values[field];

  switch (field) {
    case "email":
      if (!value) return "Email is required";
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
        return "Enter a valid email address";
      }
      return "";
    case "password":
      if (!value) return "Password is required";
      if (value.length < 8) return "Password must be at least 8 characters";
      if (!/[A-Z]/.test(value) || !/\d/.test(value)) {
        return "Must include an uppercase letter and a digit";
      }
      return "";
    case "confirmPassword":
      if (!value) return "Confirm your password";
      if (value !== values.password) return "Passwords do not match";
      return "";
    case "fullName":
      return value.trim() ? "" : "Full name is required";
    case "companyName":
      return value.trim() ? "" : "Company name is required";
    case "industry":
      return value.trim() ? "" : "Industry is required";
    case "region":
      return value.trim() ? "" : "Region is required";
    default:
      return "";
  }
}

export function validateRegisterForm(values: RegisterFormValues): Record<string, string> {
  const fields: Array<keyof RegisterFormValues> = [
    "fullName",
    "companyName",
    "industry",
    "region",
    "email",
    "password",
    "confirmPassword",
  ];

  const errors: Record<string, string> = {};
  for (const field of fields) {
    const message = validateRegisterField(field, values);
    if (message) errors[field] = message;
  }
  return errors;
}
