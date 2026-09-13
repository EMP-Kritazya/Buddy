import { Link, useNavigate } from "@tanstack/react-router";
import { useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { onboardingService } from "@/services/onboardingService";

type Answers = {
  name: string;
  university: string;
  major: string;
  level: string;
  studyHours: string;
  peakTime: string;
  distraction: string;
  needs: string[];
  goal: string;
};

const levels = ["Freshman", "Sophomore", "Junior", "Senior"];
const studyHours = ["1–2 hrs", "3–4 hrs", "5–6 hrs", "7+ hrs"];
const peakTimes = ["Early morning", "Morning", "Afternoon", "Night"];
const distractions = ["Social media", "Gaming", "YouTube", "Phone"];
const needs = [
  "Staying focused during study sessions",
  "Managing deadlines and tasks",
  "Reducing distractions",
  "Building better study habits",
  "Understanding when I'm most productive",
  "Getting coaching when I drift",
];

const inputClass =
  "w-full rounded-none border-0 border-b border-border bg-transparent px-0 py-3 font-sans text-[15px] text-ink outline-none transition-colors duration-150 placeholder:text-border focus:border-accent focus:ring-0";

const smallLabelClass = "mb-3 block text-xs font-medium text-ink-2";

function TextField({
  id,
  label,
  placeholder,
  value,
  onChange,
}: {
  id: string;
  label: string;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-xs font-medium text-ink-2">
        {label}
      </label>
      <input
        id={id}
        type="text"
        value={value}
        placeholder={placeholder}
        autoComplete="organization"
        onChange={(event) => onChange(event.target.value)}
        className={inputClass}
      />
    </div>
  );
}

function ChoiceGroup({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: string[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <fieldset>
      <legend className={smallLabelClass}>{label}</legend>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {options.map((option) => {
          const selected = value === option;
          return (
            <Button
              key={option}
              type="button"
              variant="outline"
              aria-pressed={selected}
              onClick={() => onChange(option)}
              className={`h-auto min-h-9 whitespace-normal rounded-[3px] px-4 py-2 text-[13px] font-normal shadow-none transition-colors duration-150 ${
                selected
                  ? "border-accent bg-accent-2 text-accent hover:bg-accent-2 hover:text-accent"
                  : "border-border bg-transparent text-ink-2 hover:border-ink-3 hover:bg-transparent hover:text-ink-2"
              }`}
            >
              {option}
            </Button>
          );
        })}
      </div>
    </fieldset>
  );
}

function StepHeading({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <p className="mb-8 font-mono text-[11px] text-ink-3">{label}</p>
      <h1 className="mb-10 font-serif text-[36px] font-normal leading-[1.2] text-ink">{children}</h1>
    </>
  );
}

function ValidationMessage() {
  return (
    <p className="mt-4 text-xs text-incident" role="alert">
      This helps Buddy understand you better.
    </p>
  );
}

export default function OnboardingPage() {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(1);
  const [showError, setShowError] = useState(false);
  const [validationAttempt, setValidationAttempt] = useState(0);
  // Phase 2: POST this to /api/users/onboarding
  // Tiger Data will store in onboarding_responses table
  const [answers, setAnswers] = useState<Answers>({
    name: "",
    university: "",
    major: "",
    level: "",
    studyHours: "",
    peakTime: "",
    distraction: "",
    needs: [],
    goal: "",
  });

  const updateAnswer = <Key extends keyof Answers>(key: Key, value: Answers[Key]) => {
    setAnswers((current) => ({ ...current, [key]: value }));
    setShowError(false);
  };

  const isCurrentStepValid = () => {
    if (currentStep === 1) return answers.name.trim().length > 0;
    if (currentStep === 2) return answers.university.trim().length > 0;
    if (currentStep === 3) {
      return Boolean(answers.studyHours && answers.peakTime && answers.distraction);
    }
    if (currentStep === 4) return answers.needs.length > 0;
    if (currentStep === 5) return answers.goal.trim().length > 0;
    return true;
  };

  const continueForward = () => {
    if (!isCurrentStepValid()) {
      setShowError(true);
      setValidationAttempt((attempt) => attempt + 1);
      return;
    }
    setShowError(false);
    setCurrentStep((step) => Math.min(step + 1, 6));
  };

  const goBack = () => {
    setShowError(false);
    setCurrentStep((step) => Math.max(step - 1, 1));
  };

  const toggleNeed = (need: string) => {
    updateAnswer(
      "needs",
      answers.needs.includes(need)
        ? answers.needs.filter((item) => item !== need)
        : [...answers.needs, need],
    );
  };

  const summaryGoal = answers.goal.trim()
    ? `${answers.goal.trim().slice(0, 40)}${answers.goal.trim().length > 40 ? "…" : ""}`
    : "—";

  const finishOnboarding = async () => {
    const stored = JSON.parse(window.localStorage.getItem("buddy_user") || "{}");
    await onboardingService.submit({ ...answers, name: answers.name.trim(), email: stored.email || "" });
    void navigate({ to: "/download" });
  };

  return (
    <main className="min-h-screen bg-canvas px-5 py-10 text-ink sm:px-8 md:px-12 md:py-20">
      <div className="mx-auto max-w-[640px]">
        <header className="flex items-center justify-between border-b border-border pb-5">
          <Link to="/" className="font-serif text-xl text-ink">
            Buddy
          </Link>
          <p className="font-mono text-xs text-ink-3" aria-live="polite">
            {currentStep} of 6
          </p>
        </header>

        <div className="mb-[60px] mt-[60px] h-0.5 w-full bg-border-2" aria-hidden="true">
          <div
            className="h-full bg-accent transition-[width] duration-300 ease-out motion-reduce:transition-none"
            style={{ width: `${(currentStep / 6) * 100}%` }}
          />
        </div>

        <section key={currentStep} className="buddy-step-in min-h-[390px]">
          {currentStep === 1 ? (
            <div>
              <StepHeading label="01 — About you">What should Buddy call you?</StepHeading>
              <div
                key={showError ? validationAttempt : "name"}
                className={`max-w-[320px] ${showError ? "buddy-field-shake" : ""}`}
              >
                <label htmlFor="name" className="sr-only">
                  What should Buddy call you?
                </label>
                <input
                  id="name"
                  type="text"
                  value={answers.name}
                  autoComplete="given-name"
                  placeholder="Your first name"
                  aria-invalid={showError}
                  onChange={(event) => updateAnswer("name", event.target.value)}
                  className={`${inputClass} text-2xl`}
                  autoFocus
                />
                {showError ? <ValidationMessage /> : null}
              </div>
            </div>
          ) : null}

          {currentStep === 2 ? (
            <div>
              <StepHeading label="02 — Your studies">Where are you studying?</StepHeading>
              <div
                key={showError ? validationAttempt : "education"}
                className={`space-y-6 ${showError ? "buddy-field-shake" : ""}`}
              >
                <TextField
                  id="university"
                  label="University or school"
                  placeholder="University of Texas at Arlington"
                  value={answers.university}
                  onChange={(value) => updateAnswer("university", value)}
                />
                <TextField
                  id="major"
                  label="Major or field"
                  placeholder="Computer Science"
                  value={answers.major}
                  onChange={(value) => updateAnswer("major", value)}
                />
                <ChoiceGroup
                  label="Current level"
                  options={levels}
                  value={answers.level}
                  onChange={(value) => updateAnswer("level", value)}
                />
                {showError ? <ValidationMessage /> : null}
              </div>
            </div>
          ) : null}

          {currentStep === 3 ? (
            <div>
              <StepHeading label="03 — How you work">Tell us how you study.</StepHeading>
              <div
                key={showError ? validationAttempt : "work-style"}
                className={`space-y-9 ${showError ? "buddy-field-shake" : ""}`}
              >
                <ChoiceGroup
                  label="Hours you study per day"
                  options={studyHours}
                  value={answers.studyHours}
                  onChange={(value) => updateAnswer("studyHours", value)}
                />
                <ChoiceGroup
                  label="When are you most productive?"
                  options={peakTimes}
                  value={answers.peakTime}
                  onChange={(value) => updateAnswer("peakTime", value)}
                />
                <ChoiceGroup
                  label="Biggest distraction"
                  options={distractions}
                  value={answers.distraction}
                  onChange={(value) => updateAnswer("distraction", value)}
                />
                {showError ? <ValidationMessage /> : null}
              </div>
            </div>
          ) : null}

          {currentStep === 4 ? (
            <div>
              <p className="mb-8 font-mono text-[11px] text-ink-3">04 — What you need</p>
              <h1 className="font-serif text-[36px] font-normal leading-[1.2] text-ink">
                What do you want Buddy to help with?
              </h1>
              <p className="mb-10 mt-2 text-[13px] text-ink-3">Select all that apply.</p>
              <fieldset
                key={showError ? validationAttempt : "needs"}
                className={showError ? "buddy-field-shake" : ""}
              >
                <legend className="sr-only">What Buddy should help with</legend>
                <div className="border-t border-border-2">
                  {needs.map((need) => {
                    const selected = answers.needs.includes(need);
                    return (
                      <Button
                        key={need}
                        type="button"
                        variant="ghost"
                        aria-pressed={selected}
                        onClick={() => toggleNeed(need)}
                        className="flex h-auto w-full justify-between whitespace-normal rounded-none border-b border-border-2 bg-transparent px-0 py-4 text-left text-[15px] font-normal text-ink shadow-none hover:bg-transparent hover:text-ink"
                      >
                        <span className="pr-5">{need}</span>
                        <span
                          className={`flex size-4 shrink-0 items-center justify-center rounded-[2px] border text-[11px] leading-none ${
                            selected ? "border-accent bg-accent text-surface" : "border-border"
                          }`}
                          aria-hidden="true"
                        >
                          {selected ? "✓" : ""}
                        </span>
                      </Button>
                    );
                  })}
                </div>
                {showError ? <ValidationMessage /> : null}
              </fieldset>
            </div>
          ) : null}

          {currentStep === 5 ? (
            <div>
              <p className="mb-8 font-mono text-[11px] text-ink-3">05 — Your goal</p>
              <h1 className="font-serif text-[36px] font-normal leading-[1.2] text-ink">
                What's your biggest goal this semester?
              </h1>
              <p className="mb-10 mt-2 text-[13px] text-ink-3">
                Buddy will use this to coach you.
              </p>
              <div
                key={showError ? validationAttempt : "goal"}
                className={`max-w-[480px] ${showError ? "buddy-field-shake" : ""}`}
              >
                <label htmlFor="goal" className="sr-only">
                  Biggest goal this semester
                </label>
                <textarea
                  id="goal"
                  value={answers.goal}
                  maxLength={200}
                  placeholder="Finish my senior design project and maintain a 3.9 GPA this semester."
                  aria-invalid={showError}
                  onChange={(event) => updateAnswer("goal", event.target.value)}
                  className="min-h-[100px] w-full resize-none rounded-none border-0 border-b border-border bg-transparent px-0 py-4 font-sans text-[15px] leading-[1.6] text-ink outline-none placeholder:text-border focus:border-accent focus:ring-0 md:min-h-[120px]"
                />
                <p className="mt-2 text-right font-mono text-[11px] text-ink-3">
                  {answers.goal.length} / 200
                </p>
                {showError ? <ValidationMessage /> : null}
              </div>
            </div>
          ) : null}

          {currentStep === 6 ? (
            <div>
              <p className="mb-8 font-mono text-[11px] text-ink-3">06 — You're set</p>
              <h1 className="font-serif text-[48px] font-normal leading-[1.2] text-ink">
                {answers.name.trim() ? (
                  <>
                    Buddy is ready
                    <br />
                    for you, {answers.name.trim()}.
                  </>
                ) : (
                  "Buddy is ready for you."
                )}
              </h1>
              <p className="mb-12 mt-2 max-w-[480px] text-base leading-[1.6] text-ink-2">
                Your profile is saved. Next, install the Buddy agent on your computer.
              </p>
              <dl className="mb-12 space-y-4">
                {[
                  ["Studying at", answers.university.trim() || "—"],
                  ["Peak focus", answers.peakTime || "—"],
                  ["Main goal", summaryGoal],
                ].map(([label, value]) => (
                  <div key={label} className="grid grid-cols-[92px_1fr] gap-3">
                    <dt className="font-mono text-[11px] text-ink-3">{label}</dt>
                    <dd className="text-sm text-ink">{value}</dd>
                  </div>
                ))}
              </dl>
              <Button
                type="button"
                onClick={() => void finishOnboarding()}
                className="h-auto rounded-[3px] bg-accent px-7 py-3 text-sm font-medium text-surface shadow-none hover:bg-accent hover:brightness-90"
              >
                Continue to setup
              </Button>
            </div>
          ) : null}
        </section>

        {currentStep < 6 ? (
          <nav className={`mt-16 flex items-center ${currentStep === 1 ? "justify-end" : "justify-between"}`}>
            {currentStep > 1 ? (
              <Button
                type="button"
                variant="ghost"
                onClick={goBack}
                className="h-auto rounded-none bg-transparent px-0 py-2 text-[13px] font-normal text-ink-3 shadow-none hover:bg-transparent hover:text-ink"
              >
                ← Back
              </Button>
            ) : null}
            <Button
              type="button"
              onClick={continueForward}
              className="h-auto rounded-[3px] bg-accent px-6 py-2.5 text-sm font-medium text-surface shadow-none hover:bg-accent hover:brightness-90"
            >
              Continue →
            </Button>
          </nav>
        ) : null}
      </div>
    </main>
  );
}
