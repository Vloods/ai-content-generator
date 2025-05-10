export const extractErrorMessage = (error) => {
  if (!error.response) {
    return 'Network error occurred';
  }

  const { data } = error.response;
  
  // Handle validation errors
  if (data.detail && Array.isArray(data.detail)) {
    return data.detail.map(err => err.msg).join(', ');
  }
  
  // Handle single error message
  if (typeof data.detail === 'string') {
    return data.detail;
  }
  
  // Handle other error formats
  if (data.msg) {
    return Array.isArray(data.msg) ? data.msg[0] : data.msg;
  }
  
  return 'An error occurred';
}; 