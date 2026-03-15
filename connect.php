<?php
  $host_name = 'db5019085281.hosting-data.io';
  $database = 'dbs15008512';
  $user_name = 'dbu1059715';
  $password = 'devdbz2026';

  $link = new mysqli($host_name, $user_name, $password, $database);

  if ($link->connect_error) {
    die('<p>Verbindung zum MySQL Server fehlgeschlagen: '. $link->connect_error .'</p>');
  } else {
    echo '<p>Verbindung zum MySQL Server erfolgreich aufgebaut.</p>';
  }
?>