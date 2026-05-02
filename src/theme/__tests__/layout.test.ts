import { createTheme } from '@mui/material/styles';
import {
  CONTENT_CONTAINER_PADDING,
  contentContainerRootStyles,
  contentContainerSx,
  pageContentSx
} from 'src/theme/layout';

describe('layout spacing', () => {
  it('uses the report padding token for standard containers', () => {
    const theme = createTheme();
    const styles = contentContainerRootStyles(theme);

    expect(CONTENT_CONTAINER_PADDING).toEqual({ xs: 1.5, sm: 2 });
    expect(contentContainerSx.px).toEqual(CONTENT_CONTAINER_PADDING);
    expect(pageContentSx.p).toEqual(CONTENT_CONTAINER_PADDING);
    expect(styles.paddingLeft).toBe('12px');
    expect(styles.paddingRight).toBe('12px');
    expect(styles['@media (min-width:600px)']).toEqual({
      paddingLeft: '16px',
      paddingRight: '16px'
    });
  });
});
