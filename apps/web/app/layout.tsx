import "./globals.css";
export const metadata = {
  title: "Fieldnote | Market Research",
  description: "Evidence-led company research, reviewed by you.",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
