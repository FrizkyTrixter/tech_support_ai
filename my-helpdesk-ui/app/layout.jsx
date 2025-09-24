// app/layout.jsx
import './globals.css';

export const metadata = { title: 'IT Helpdesk' };

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
