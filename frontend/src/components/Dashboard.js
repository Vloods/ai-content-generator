import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Typography,
  TextField,
  Button,
  Box,
  Paper,
  CircularProgress,
  Snackbar,
  Alert,
  AppBar,
  Toolbar,
  IconButton,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import { extractErrorMessage } from '../utils/errorHandler';
import LogoutIcon from '@mui/icons-material/Logout';

const TARIFFS = [
  { value: 'standart', label: 'Standard (1B)', cost: 1 },
  { value: 'pro', label: 'Pro (4B)', cost: 4 },
  { value: 'premium', label: 'Premium (12B)', cost: 12 },
];

const Dashboard = () => {
  const { api, logout } = useAuth();
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState('');
  const [result, setResult] = useState('');
  const [balance, setBalance] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [tariff, setTariff] = useState('standart');

  const fetchBalance = useCallback(async () => {
    try {
      setLoading(true);
      const response = await api.get('/balance');
      setBalance(response.data.new_balance);
    } catch (error) {
      console.error('Error fetching balance:', error);
      setError(extractErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    fetchBalance();
  }, [fetchBalance]);

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      setError('Please enter a prompt');
      return;
    }

    try {
      setLoading(true);
      setError('');
      const response = await api.post('/generate', { 
        prompt,
        tariff,
      });
      setResult(response.data.text);
      await fetchBalance();
    } catch (error) {
      console.error('Error generating content:', error);
      setError(extractErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  const handleAddBalance = async () => {
    try {
      setLoading(true);
      setError('');
      const response = await api.post('/balance?amount=100.0');
      setBalance(response.data.new_balance);
      setSuccess('Balance updated successfully');
    } catch (error) {
      console.error('Error adding balance:', error);
      setError(extractErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <Box sx={{ flexGrow: 1 }}>
      <AppBar position="static" color="primary" elevation={0}>
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            AI Content Generator
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Typography variant="body1">
              Balance: {balance} credits
            </Typography>
            <Button
              variant="contained"
              color="secondary"
              onClick={handleAddBalance}
              disabled={loading}
              size="small"
            >
              Add 100 Credits
            </Button>
            <IconButton color="inherit" onClick={handleLogout}>
              <LogoutIcon />
            </IconButton>
          </Box>
        </Toolbar>
      </AppBar>

      <Container maxWidth="md" sx={{ mt: 4, mb: 4 }}>
        <Paper 
          elevation={3} 
          sx={{ 
            p: 4, 
            borderRadius: 2,
            background: 'linear-gradient(145deg, #ffffff 0%, #f5f5f5 100%)'
          }}
        >
          <Typography variant="h5" gutterBottom sx={{ mb: 3, color: 'primary.main' }}>
            Generate Content
          </Typography>

          <FormControl fullWidth sx={{ mb: 3 }}>
            <InputLabel>Select Model</InputLabel>
            <Select
              value={tariff}
              label="Select Model"
              onChange={(e) => setTariff(e.target.value)}
              disabled={loading}
            >
              {TARIFFS.map((t) => (
                <MenuItem key={t.value} value={t.value}>
                  {t.label} ({t.cost} credits)
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <TextField
            fullWidth
            multiline
            rows={4}
            variant="outlined"
            label="Enter your prompt"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            disabled={loading}
            sx={{ 
              mb: 3,
              '& .MuiOutlinedInput-root': {
                '&:hover fieldset': {
                  borderColor: 'primary.main',
                },
              },
            }}
          />
          <Button
            variant="contained"
            color="primary"
            onClick={handleGenerate}
            disabled={loading || !prompt.trim()}
            size="large"
            sx={{ 
              mb: 3,
              minWidth: 200,
              height: 48,
              borderRadius: 2,
              textTransform: 'none',
              fontSize: '1.1rem',
            }}
          >
            {loading ? <CircularProgress size={24} color="inherit" /> : 'Generate'}
          </Button>

          {result && (
            <Box sx={{ mt: 4 }}>
              <Typography variant="h6" gutterBottom sx={{ color: 'primary.main' }}>
                Generated Result:
              </Typography>
              <Paper 
                elevation={1} 
                sx={{ 
                  p: 3, 
                  bgcolor: 'grey.50',
                  borderRadius: 2,
                  border: '1px solid',
                  borderColor: 'divider',
                }}
              >
                <Typography sx={{ whiteSpace: 'pre-wrap' }}>
                  {result}
                </Typography>
              </Paper>
            </Box>
          )}
        </Paper>
      </Container>

      <Snackbar
        open={!!error}
        autoHideDuration={6000}
        onClose={() => setError('')}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert 
          severity="error" 
          onClose={() => setError('')}
          sx={{ width: '100%' }}
        >
          {error}
        </Alert>
      </Snackbar>

      <Snackbar
        open={!!success}
        autoHideDuration={6000}
        onClose={() => setSuccess('')}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert 
          severity="success" 
          onClose={() => setSuccess('')}
          sx={{ width: '100%' }}
        >
          {success}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default Dashboard; 