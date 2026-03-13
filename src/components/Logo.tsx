import React from 'react';

function Logo(props: React.ImgHTMLAttributes<HTMLImageElement>) {
  return (
    <img
      alt="Logo"
      src="/static/images/logo-horizontal-with-text-white.png"
      height="50"
      {...props}
    />
  );
}

export default Logo;
