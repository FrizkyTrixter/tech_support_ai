export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <title>Helpdesk UI</title>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        {/* Tailwind via CDN for styling */}
        <link
          href="https://cdn.jsdelivr.net/npm/tailwindcss@3.3.2/dist/tailwind.min.css"
          rel="stylesheet"
        />
        <link rel="icon" href="/favicon.ico" />
      </head>
      <body className="bg-[#001F3F]">
        {children}
      </body>
    </html>
  );
}
