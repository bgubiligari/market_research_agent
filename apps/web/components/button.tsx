import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
const variants = cva("button", {
  variants: { variant: { default: "primary", outline: "outline" } },
  defaultVariants: { variant: "default" },
});
export function Button({
  className,
  variant,
  asChild = false,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof variants> & { asChild?: boolean }) {
  const Component = asChild ? Slot : "button";
  return (
    <Component
      className={twMerge(clsx(variants({ variant }), className))}
      {...props}
    />
  );
}
