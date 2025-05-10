import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import {
  Box,
  Container,
  Typography,
  Card,
  CardContent,
  Grid,
  Pagination,
  CircularProgress,
  Chip,
  Alert,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Collapse,
  Button,
} from '@mui/material';
import { format } from 'date-fns';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import { useNavigate } from 'react-router-dom';

// Default API URL if environment variable is not set
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const GenerationRow = ({ generation }) => {
  const [open, setOpen] = useState(false);

  return (
    <>
      <TableRow sx={{ '& > *': { borderBottom: 'unset' } }}>
        <TableCell>
          <IconButton
            aria-label="expand row"
            size="small"
            onClick={() => setOpen(!open)}
          >
            {open ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
          </IconButton>
        </TableCell>
        <TableCell>{format(new Date(generation.created_at), 'PPpp')}</TableCell>
        <TableCell>
          <Chip
            label={`${generation.tariff} (${generation.cost.toFixed(2)} credits)`}
            color="primary"
            size="small"
          />
        </TableCell>
        <TableCell>{generation.processing_time.toFixed(2)}s</TableCell>
      </TableRow>
      <TableRow>
        <TableCell style={{ paddingBottom: 0, paddingTop: 0 }} colSpan={4}>
          <Collapse in={open} timeout="auto" unmountOnExit>
            <Box sx={{ margin: 2 }}>
              <Typography variant="h6" gutterBottom component="div">
                Details
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12}>
                  <Typography variant="subtitle1" gutterBottom>
                    Prompt:
                  </Typography>
                  <Typography variant="body1" paragraph>
                    {generation.prompt}
                  </Typography>
                </Grid>
                <Grid item xs={12}>
                  <Typography variant="subtitle1" gutterBottom>
                    Response:
                  </Typography>
                  <Typography variant="body1" paragraph>
                    {generation.result}
                  </Typography>
                </Grid>
              </Grid>
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </>
  );
};

const History = () => {
  const { token, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [history, setHistory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const pageSize = 10;

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
  }, [isAuthenticated, navigate]);

  const fetchHistory = React.useCallback(async (pageNum) => {
    try {
      setLoading(true);
      setError(null);
      console.log('Fetching history...');
      console.log('API URL:', API_URL);
      console.log('Token:', token ? 'Present' : 'Missing');
      
      if (!token) {
        throw new Error('Authentication token is missing');
      }

      const response = await axios.get(
        `${API_URL}/history?page=${pageNum}&page_size=${pageSize}`,
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );
      
      console.log('History response:', response.data);
      if (!response.data.generations) {
        console.error('No generations array in response:', response.data);
        setError('Invalid response format from server');
        return;
      }
      
      setHistory(response.data);
    } catch (error) {
      console.error('Error fetching history:', error);
      console.error('Error details:', error.response?.data || error.message);
      setError(error.response?.data?.detail || error.message);
      setHistory({ generations: [], total_count: 0, page: pageNum, page_size: pageSize });
    } finally {
      setLoading(false);
    }
  }, [token, pageSize]);

  useEffect(() => {
    if (isAuthenticated && token) {
      console.log('History component mounted/updated');
      console.log('Current page:', page);
      console.log('Token present:', !!token);
      fetchHistory(page);
    }
  }, [page, fetchHistory, isAuthenticated, token]);

  const handlePageChange = (event, value) => {
    setPage(value);
  };

  if (!isAuthenticated) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Please log in to view your history
        </Typography>
        <Button
          variant="contained"
          color="primary"
          onClick={() => navigate('/login')}
          sx={{ mt: 2 }}
        >
          Go to Login
        </Button>
      </Container>
    );
  }

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" component="h1" gutterBottom>
        Generation History
      </Typography>
      
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      
      {!error && history?.generations.length === 0 ? (
        <Typography variant="body1" color="text.secondary">
          No generation history found.
        </Typography>
      ) : (
        <>
          <Card sx={{ mb: 4 }}>
            <CardContent>
              <TableContainer component={Paper}>
                <Table aria-label="generation history">
                  <TableHead>
                    <TableRow>
                      <TableCell />
                      <TableCell>Date</TableCell>
                      <TableCell>Tariff</TableCell>
                      <TableCell>Processing Time</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {history?.generations.map((generation) => (
                      <GenerationRow key={generation.id} generation={generation} />
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
          
          <Box display="flex" justifyContent="center" mt={4}>
            <Pagination
              count={Math.ceil(history?.total_count / pageSize)}
              page={page}
              onChange={handlePageChange}
              color="primary"
            />
          </Box>
        </>
      )}
    </Container>
  );
};

export default History; 