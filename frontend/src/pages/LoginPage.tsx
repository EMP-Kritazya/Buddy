import { Link, useNavigate } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";
import { z } from "zod";

import { AuthField, AuthPageLayout } from "@/components/auth/AuthPageLayout";
import { authService } from "@/services/authService";

const loginSchema = z.object({
  email: z.string().trim().min(1, "Enter your email.").email("Enter a valid email address.").max(255, "Email must be 255 characters or fewer."),
  password: z.string().min(1, "Enter your password.").max(128, "Password must be 128 characters or fewer."),
});

type LoginValues = z.infer<typeof loginSchema>;
type LoginErrors = Record<keyof LoginValues, string | undefined>;

export default function LoginPage() {
  const navigate = useNavigate();
  const [values, setValues] = useState<LoginValues>({ email: "", password: "" });
  const [errors, setErrors] = useState<LoginErrors>({ email: undefined, password: undefined });

  const updateField = (field: keyof LoginValues, value: string) => {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const result = loginSchema.safeParse(values);

    if (!result.success) {
      const fieldErrors = result.error.flatten().fieldErrors;
      setErrors({ email: fieldErrors.email?.[0], password: fieldErrors.password?.[0] });
      return;
    }

    await authService.login(result.data.email, result.data.password);
    void navigate({ to: "/dashboard" });
  };

  return (
    <AuthPageLayout statement="Good to have you back.">
      <Link to="/" className="mb-12 hidden text-[13px] text-ink-3 transition-colors duration-150 hover:text-ink md:block">
        ← Back to home
      </Link>

      <h1 className="font-serif text-[40px] font-normal leading-tight text-ink">Sign in</h1>
      <p className="mt-2 text-sm text-ink-3">Your focus data is waiting.</p>

      <form className="mt-10" noValidate onSubmit={handleSubmit}>
        <div className="space-y-5">
          <AuthField
            id="email"
            label="Email"
            type="email"
            placeholder="you@university.edu"
            autoComplete="email"
            value={values.email}
            error={errors.email}
            onChange={(value) => updateField("email", value)}
          />
          <AuthField
            id="password"
            label="Password"
            type="password"
            placeholder="Your password"
            autoComplete="current-password"
            value={values.password}
            error={errors.password}
            hint={<span className="block text-right">Forgot password?</span>}
            onChange={(value) => updateField("password", value)}
          />
        </div>

        <button type="submit" className="mt-8 w-full rounded-[3px] border-0 bg-accent px-6 py-3 text-sm font-medium text-surface transition-[filter] duration-150 hover:brightness-90">
          Sign in
        </button>
      </form>

      <div className="mt-6 border-t border-border pt-5 text-[13px] text-ink-3">
        Don't have an account?{" "}
        <Link to="/signup" className="text-accent underline underline-offset-2">Get started</Link>
      </div>
    </AuthPageLayout>
  );
}
