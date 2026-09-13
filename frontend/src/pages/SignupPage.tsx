import { Link, useNavigate } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";
import { z } from "zod";

import { AuthField, AuthPageLayout } from "@/components/auth/AuthPageLayout";
import { authService } from "@/services/authService";

const signupSchema = z.object({
  name: z.string().trim().min(1, "Enter your full name.").max(100, "Name must be 100 characters or fewer."),
  email: z.string().trim().min(1, "Enter your email.").email("Enter a valid email address.").max(255, "Email must be 255 characters or fewer."),
  password: z.string().min(1, "Enter a password.").min(8, "Password must be at least 8 characters.").max(128, "Password must be 128 characters or fewer."),
});

type SignupValues = z.infer<typeof signupSchema>;
type SignupErrors = Record<keyof SignupValues, string | undefined>;

export default function SignupPage() {
  const navigate = useNavigate();
  const [values, setValues] = useState<SignupValues>({ name: "", email: "", password: "" });
  const [errors, setErrors] = useState<SignupErrors>({ name: undefined, email: undefined, password: undefined });

  const updateField = (field: keyof SignupValues, value: string) => {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const result = signupSchema.safeParse(values);

    if (!result.success) {
      const fieldErrors = result.error.flatten().fieldErrors;
      setErrors({
        name: fieldErrors.name?.[0],
        email: fieldErrors.email?.[0],
        password: fieldErrors.password?.[0],
      });
      return;
    }

    await authService.signup(result.data.email, result.data.password);
    void navigate({ to: "/onboarding" });
  };

  return (
    <AuthPageLayout statement={<>Understanding your attention<br />starts with one step.</>}>
      <Link to="/" className="mb-12 hidden text-[13px] text-ink-3 transition-colors duration-150 hover:text-ink md:block">
        ← Back to home
      </Link>

      <h1 className="font-serif text-[40px] font-normal leading-tight text-ink">Create your account</h1>
      <p className="mt-2 text-sm text-ink-3">Free during HackRice 16.</p>

      <form className="mt-10" noValidate onSubmit={handleSubmit}>
        <div className="space-y-5">
          <AuthField
            id="name"
            label="Full name"
            type="text"
            placeholder="Sandesh Dhakal"
            autoComplete="name"
            value={values.name}
            error={errors.name}
            onChange={(value) => updateField("name", value)}
          />
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
            placeholder="Min. 8 characters"
            autoComplete="new-password"
            value={values.password}
            error={errors.password}
            hint="Use something you'll remember."
            onChange={(value) => updateField("password", value)}
          />
        </div>

        <button type="submit" className="mt-8 w-full rounded-[3px] border-0 bg-accent px-6 py-3 text-sm font-medium text-surface transition-[filter] duration-150 hover:brightness-90">
          Create account
        </button>
      </form>

      <div className="mt-6 border-t border-border pt-5 text-[13px] text-ink-3">
        Already have an account?{" "}
        <Link to="/login" className="text-accent underline underline-offset-2">Sign in</Link>
      </div>
    </AuthPageLayout>
  );
}
