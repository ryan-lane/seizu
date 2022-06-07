import { createStyles, makeStyles } from '@mui/styles';

const useStyles = makeStyles(() =>
  createStyles({
    '@global': {
      '*': {
        boxSizing: 'border-box',
        margin: 0,
        padding: 0
      },
      html: {
        '-webkit-font-smoothing': 'antialiased',
        '-moz-osx-font-smoothing': 'grayscale'
      },
      body: {
        backgroundColor: '#f4f6f8',
        height: '100%',
        width: '100%'
      },
      a: {
        textDecoration: 'none'
      },
      '#root': {
        height: '100%',
        width: '100%'
      },
      '.mui-markdown-ol': {
        paddingLeft: 40,
        paddingTop: 10,
        paddingBottom: 10
      },
      '.mui-markdown-ul': {
        paddingLeft: 40,
        paddingTop: 10,
        paddingBottom: 10
      }
    }
  })
);

function GlobalStyles() {
  useStyles();

  return null;
}

export default GlobalStyles;
