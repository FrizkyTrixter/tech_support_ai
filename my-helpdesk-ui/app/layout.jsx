// app/layout.jsx
import './globals.css';

export const metadata = {
  title: 'IT Helpdesk',
  description: 'Helpdesk chat UI',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
